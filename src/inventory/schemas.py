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
    status: StatusEmTransito
    quantidade_pendente: int
    data_prevista_entrega: date | None


class EmTransito(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_unidades: int
    itens: list[ItemEmTransito]
