"""DTOs de domínio do módulo `sales`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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


# `VendasDoMes` e `VendasDoDia` são dataclasses, não modelos pydantic: o retrato do estoque
# inteiro traz centenas de milhares delas e a validação pesa no tempo do painel.
@dataclass(frozen=True, slots=True)
class VendasDoMes:
    """Soma das vendas de um SKU num mês, em UTC. `primeira_venda` é a data da primeira
    venda do mês: com o histórico inteiro, a do primeiro mês é a primeira venda do SKU."""

    ano: int
    mes: int
    quantidade: int
    primeira_venda: datetime


@dataclass(frozen=True, slots=True)
class VendasDoDia:
    """Soma das vendas de um SKU num dia, em UTC."""

    dia: date
    quantidade: int


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
