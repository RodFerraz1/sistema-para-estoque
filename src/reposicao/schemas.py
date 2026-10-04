"""DTOs de domínio do módulo `reposicao`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU

ResultadoVerificacao = Literal["repus", "estava_na_gondola", "sem_estoque_no_deposito"]


class DiaObservado(BaseModel):
    model_config = ConfigDict(frozen=True)

    dia: date
    quantidade: int


class QuedaDeVenda(BaseModel):
    """A venda de um SKU nos últimos dias abertos ficou muito abaixo da venda diária base.
    `ultimos_dias` é a janela observada, do mais antigo ao mais recente. `probabilidade` é a
    chance de vender no máximo o que vendeu se a venda seguisse a base."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    venda_diaria_base: float
    ultimos_dias: list[DiaObservado]
    probabilidade: float

    @property
    def vendido_na_janela(self) -> int:
        return sum(d.quantidade for d in self.ultimos_dias)

    @property
    def venda_perdida(self) -> float:
        """O que a base esperava vender na janela menos o que vendeu."""
        return self.venda_diaria_base * len(self.ultimos_dias) - self.vendido_na_janela


class Setor(BaseModel):
    """Setor da loja, numa lista simples mantida pelo admin. O nome é único, sem diferenciar
    maiúsculas. Setor inativo não aparece para a vendedora nem para o repositor."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    nome: str
    ativo: bool


class SetorDoSku(BaseModel):
    """O setor conhecido de um SKU: o do último aviso de gôndola vazia ou o que a verificação
    corrigiu. O ERP não tem essa informação. `usuario_id` é nulo no que veio do seed."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    setor_id: UUID
    atualizado_em: datetime
    usuario_id: UUID | None


class AvisoGondola(BaseModel):
    """Recado da vendedora ao repositor: a gôndola do SKU está vazia. Fica aberto até uma
    verificação de gôndola do mesmo SKU registrada depois dele: não há coluna de status.
    `disponivel_no_erp` é o do momento; `avisado_por`, o nome de quem avisou."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    setor_id: UUID
    comentario: str | None
    disponivel_no_erp: int
    avisado_por: str
    usuario_id: UUID
    criado_em: datetime


class ItemQuedaDeVenda(BaseModel):
    """SKU com queda de venda e estoque disponível: provavelmente falta na gôndola. `setor`
    é o setor conhecido do SKU."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    queda: QuedaDeVenda
    setor: Setor | None = None


class ItemAvisoGondola(BaseModel):
    """SKU com aviso de gôndola vazia aberto. `avisos` vem do mais antigo para o mais recente.
    `queda` é a queda de venda quando o SKU também estaria nesse grupo do painel."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    avisos: list[AvisoGondola]
    queda: QuedaDeVenda | None
    setor: Setor | None


class FiltroReposicao(BaseModel):
    """Vazio, não filtra. `busca` segue a regra do `catalog.buscar_skus`."""

    model_config = ConfigDict(frozen=True)

    busca: str | None = None
    categoria: str | None = None
    setor_id: UUID | None = None


class PainelDoRepositor(BaseModel):
    """`avisos_de_gondola` vem do aviso aberto mais antigo para o mais recente e
    `quedas_de_venda`, da maior venda perdida para a menor. Um SKU fica num grupo só."""

    model_config = ConfigDict(frozen=True)

    avisos_de_gondola: list[ItemAvisoGondola]
    quedas_de_venda: list[ItemQuedaDeVenda]


class VerificacaoGondola(BaseModel):
    """O que o repositor achou ao olhar a gôndola de um SKU. `disponivel_no_erp` é o
    disponível do ERP no momento; `verificado_por`, o nome de quem verificou."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    resultado: ResultadoVerificacao
    comentario: str | None
    disponivel_no_erp: int
    verificado_por: str
    usuario_id: UUID
    criado_em: datetime


class MeuAvisoGondola(BaseModel):
    """Aviso de gôndola vazia de uma vendedora com a verificação que o fechou: a primeira do
    SKU registrada depois dele. Sem verificação, o aviso aguarda o repositor."""

    model_config = ConfigDict(frozen=True)

    aviso: AvisoGondola
    sku: SKU
    setor: Setor
    verificacao: VerificacaoGondola | None
