"""DTOs de domínio do módulo `inventory`."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field

from src.politica_compra.schemas import DIAS_POR_MES


def dias_de_cobertura(meses: float) -> float:
    """A cobertura em dias, como as pessoas a veem (ADR-0006): disponível dividido pela
    venda média diária, que é o giro dividido por 30. O domínio guarda meses e esta é a
    única conversão."""
    return meses * DIAS_POR_MES


class Estoque(BaseModel):
    model_config = ConfigDict(frozen=True)

    quantidade_disponivel: int
    quantidade_reservada: int
    atualizado_em: datetime


class Movimentacao(BaseModel):
    """Entrada ou saída de estoque de um SKU.

    `referencia_tipo`/`referencia_id` apontam pro documento que originou a
    movimentação (pedido de compra, venda); ambos são `None` para ajustes
    manuais.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_id: UUID
    tipo: str
    quantidade: int
    data: datetime
    referencia_tipo: str | None
    referencia_id: UUID | None
    observacao: str | None


class Cobertura(BaseModel):
    """Cobertura em meses, e em dias para as pessoas.

    `sem_giro=True` sinaliza que o SKU não teve vendas na janela e portanto
    o cálculo `estoque / giro` é indefinido. Nesse caso `meses` e `dias` são `None`.
    """

    model_config = ConfigDict(frozen=True)

    meses: float | None
    sem_giro: bool

    @computed_field
    @property
    def dias(self) -> float | None:
        return None if self.meses is None else dias_de_cobertura(self.meses)


class SKUAbaixoDoPiso(BaseModel):
    """SKU com cobertura abaixo do piso configurado.

    SKUs sem giro (cobertura indefinida) nunca aparecem aqui - sem demanda,
    não há alerta de reposição.
    """

    model_config = ConfigDict(frozen=True)

    sku_id: UUID
    sku_code: str
    produto_nome: str
    cobertura_meses: float

    @computed_field
    @property
    def cobertura_dias(self) -> float:
        return dias_de_cobertura(self.cobertura_meses)


StatusEmTransito = Literal["aprovado", "enviado", "recebido_parcial"]
STATUS_EM_TRANSITO: tuple[str, ...] = get_args(StatusEmTransito)


class ItemEmTransito(BaseModel):
    """Item de pedido de compra aberto com quantidade ainda por chegar."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    fornecedor_id: UUID
    fornecedor_nome: str
    status: StatusEmTransito
    quantidade_pendente: int
    data_prevista_entrega: date | None


class EmTransito(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_unidades: int
    itens: list[ItemEmTransito]


class EntregaRecebida(BaseModel):
    """Pedido de compra `recebido_total` com data prevista: quando devia chegar e quando chegou."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    data_prevista_entrega: date
    recebido_em: datetime


def dias_de_atraso(data_prevista: date | None, hoje: date) -> int | None:
    """Dias desde a data prevista de entrega, só quando ela já passou. Sem data prevista,
    nunca há atraso."""
    if data_prevista is None or data_prevista >= hoje:
        return None
    return (hoje - data_prevista).days


class EntregaAtrasada(BaseModel):
    """Item de pedido de compra aberto, com quantidade pendente e a data prevista de entrega
    já vencida."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    fornecedor_id: UUID
    fornecedor_nome: str
    sku_code: str
    status: StatusEmTransito
    quantidade_pendente: int
    data_prevista_entrega: date
    dias_de_atraso: int


class AtrasoRecebido(BaseModel):
    """Entrega recebida depois da data prevista."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    data_prevista_entrega: date
    recebido_em: datetime
    dias_de_atraso: int


class HistoricoDeAtrasos(BaseModel):
    """As entregas recebidas de um fornecedor e as que chegaram atrasadas, do recebimento
    mais recente para o mais antigo. A média é só das atrasadas, nula sem nenhuma."""

    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    entregas_recebidas: int
    atrasos: list[AtrasoRecebido]

    @property
    def media_dias_de_atraso(self) -> float | None:
        if not self.atrasos:
            return None
        return sum(a.dias_de_atraso for a in self.atrasos) / len(self.atrasos)
