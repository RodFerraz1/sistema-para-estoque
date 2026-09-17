"""DTOs de domínio do módulo `sales`."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Venda(BaseModel):
    """Uma venda individual de um SKU para um cliente varejista."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku_id: UUID
    quantidade: int
    valor_unitario_reais: int
    data: datetime
    cliente_ref: str


class GiroMedioMensal(BaseModel):
    model_config = ConfigDict(frozen=True)

    unidades_por_mes: float
    meses_considerados: int
    total_unidades: int


class VendaMensal(BaseModel):
    """Vendas agregadas de um SKU num mês fechado.

    `ano` e `mes` identificam o mês (1-12). `valor_total_reais` é a soma de
    `quantidade * valor_unitario` de todas as vendas naquele mês.
    """

    model_config = ConfigDict(frozen=True)

    ano: int
    mes: int
    quantidade_unidades: int
    valor_total_reais: int


class Sazonalidade(BaseModel):
    """Multiplicador sazonal por mês do ano.

    `multiplicadores` mapeia mês (1-12) para um float. Valor 1.0 = mês médio;
    >1.0 = mês acima da média; <1.0 = abaixo. `meses_considerados` diz quantos
    meses de histórico foram usados no cálculo (0 quando não há vendas).
    """

    model_config = ConfigDict(frozen=True)

    multiplicadores: dict[int, float]
    meses_considerados: int
