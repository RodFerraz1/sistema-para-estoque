"""DTOs de domínio do módulo `reposicao`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.catalog.schemas import SKU

ResultadoVerificacao = Literal["repus", "estava_na_gondola", "sem_estoque_no_deposito"]
Prioridade = Literal["mais_de_um_motivo", "parou_de_vender", "gondola_vazia", "hora_de_repor"]


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
    `disponivel_no_erp` é o do momento; `avisado_por`, o nome de quem avisou. `pecas`:
    quantas peças a vendedora pede para levar do depósito, nula quando ela não disse."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_code: str
    setor_id: UUID
    comentario: str | None
    disponivel_no_erp: int
    avisado_por: str
    usuario_id: UUID
    criado_em: datetime
    pecas: int | None = None


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


class ItemHoraDeRepor(BaseModel):
    """SKU de um produto com capacidade da gôndola cuja gôndola, pelo que vendeu desde a
    última verificação `repus`, segura no máximo `piso_gondola_dias` dias de venda, e que
    tem no estoque mais do que se estima na gôndola. `pecas_no_mix` é o que o mix de gôndola
    de hoje põe dele; `venda_media_diaria`, a do mix."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    disponivel: int
    pecas_no_mix: int
    venda_media_diaria: float
    reposicao: VerificacaoGondola
    vendido_desde: int
    setor: Setor | None = None

    @property
    def na_gondola(self) -> int:
        """Estimativa das peças ainda na gôndola, nunca negativa."""
        return max(self.pecas_no_mix - self.vendido_desde, 0)

    @property
    def dias_na_gondola(self) -> float:
        return self.na_gondola / self.venda_media_diaria

    @property
    def a_repor(self) -> int:
        """Quantas peças levar do depósito para a gôndola voltar ao mix. O disponível do ERP
        inclui o que está na gôndola."""
        return min(self.pecas_no_mix, self.disponivel) - self.na_gondola


class FiltroReposicao(BaseModel):
    """Vazio, não filtra. `busca` segue a regra do `catalog.buscar_skus`."""

    model_config = ConfigDict(frozen=True)

    busca: str | None = None
    categoria: str | None = None
    setor_id: UUID | None = None


class PainelDoRepositor(BaseModel):
    """`avisos_de_gondola` vem do aviso aberto mais antigo para o mais recente,
    `quedas_de_venda` da maior venda perdida para a menor e `hora_de_repor` de quem segura
    menos dias na gôndola para quem segura mais. Um SKU fica num grupo só."""

    model_config = ConfigDict(frozen=True)

    avisos_de_gondola: list[ItemAvisoGondola]
    quedas_de_venda: list[ItemQuedaDeVenda]
    hora_de_repor: list[ItemHoraDeRepor] = []


class ItemDoDashboard(BaseModel):
    """Uma gôndola a repor no dashboard do repositor. `queda`, `avisos` e `hora_de_repor`
    são os motivos; com mais de um, a prioridade é `mais_de_um_motivo`. `a_repor`: quantas
    peças levar do depósito, nulo quando não se sabe."""

    model_config = ConfigDict(frozen=True)

    prioridade: Prioridade
    sku: SKU
    disponivel: int
    setor: Setor | None
    queda: QuedaDeVenda | None = None
    avisos: list[AvisoGondola] = []
    hora_de_repor: ItemHoraDeRepor | None = None
    a_repor: int | None = None


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


class CapacidadeGondola(BaseModel):
    """Quantas peças de um produto do catálogo, de todas as cores e tamanhos, cabem na
    gôndola, informadas pelo repositor. Vale a última."""

    model_config = ConfigDict(frozen=True)

    produto_id: UUID
    capacidade: int = Field(gt=0)
    usuario_id: UUID
    atualizado_em: datetime


class ProdutoDaGondola(BaseModel):
    """Produto do catálogo com SKU ativo. `skus` conta as cores e tamanhos ativos."""

    model_config = ConfigDict(frozen=True)

    produto_id: UUID
    produto_nome: str
    categoria: str
    skus: int
    capacidade: CapacidadeGondola | None


class SkuNoMix(BaseModel):
    """Um SKU ativo do produto no mix de gôndola. `participacao` é a venda dele dividida pela
    venda do produto nos dias abertos do período (zero sem venda no produto). `quantidade` é
    quantas peças pôr na gôndola, nula sem capacidade."""

    model_config = ConfigDict(frozen=True)

    sku: SKU
    vendido: int
    venda_media_diaria: float
    participacao: float
    disponivel: int
    quantidade: int | None


class MixDeGondola(BaseModel):
    """`capacidade` é a usada na conta: a informada ou, sem ela, a gravada. `skus` vem da
    maior participação para a menor (o código desempata)."""

    model_config = ConfigDict(frozen=True)

    produto: ProdutoDaGondola
    capacidade: int | None
    dias_abertos: int
    skus: list[SkuNoMix]


class SugestaoDeReposicao(BaseModel):
    """Quantas peças levar do depósito para a gôndola vazia de um SKU: as do mix de gôndola
    de hoje. `pecas` nula quando o produto não tem capacidade da gôndola; zero quando o mix
    não põe nenhuma peça dele (sem disponível, ou não coube)."""

    model_config = ConfigDict(frozen=True)

    pecas: int | None
    capacidade: int | None
    disponivel: int


class MeuAvisoGondola(BaseModel):
    """Aviso de gôndola vazia de uma vendedora com a verificação que o fechou: a primeira do
    SKU registrada depois dele. Sem verificação, o aviso aguarda o repositor."""

    model_config = ConfigDict(frozen=True)

    aviso: AvisoGondola
    sku: SKU
    setor: Setor
    verificacao: VerificacaoGondola | None
