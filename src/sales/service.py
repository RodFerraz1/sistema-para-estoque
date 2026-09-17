"""Módulo `sales`: sabe sobre venda e giro.

Nesta fatia, expõe apenas `giro_medio_mensal`. `historico_vendas` e
`sazonalidade` ficam para specs futuras.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.erp_adapter.port import ERPAdapter
from src.sales.schemas import GiroMedioMensal

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _subtract_months(dt: datetime, months: int) -> datetime:
    month = dt.month - months
    year = dt.year
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month)


def _months_between(inicio: datetime, fim: datetime) -> int:
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


class Sales:
    def __init__(self, erp: ERPAdapter, *, now: datetime | None = None) -> None:
        self._erp = erp
        self._now = now

    def _agora(self) -> datetime:
        return self._now or datetime.now(UTC)

    def giro_medio_mensal(self, sku_id: UUID, meses: int = 6) -> GiroMedioMensal:
        fim = _start_of_month(self._agora())
        janela_inicio = _subtract_months(fim, meses)

        todas = self._erp.list_vendas(sku_id, _EPOCH)
        fechadas = [v for v in todas if v.data < fim]
        if not fechadas:
            return GiroMedioMensal(
                unidades_por_mes=0.0, meses_considerados=0, total_unidades=0
            )

        primeira = min(v.data for v in fechadas)
        meses_disponiveis = _months_between(_start_of_month(primeira), fim)
        divisor = max(1, min(meses, meses_disponiveis))

        na_janela = [v for v in fechadas if v.data >= janela_inicio]
        total = sum(v.quantidade for v in na_janela)
        return GiroMedioMensal(
            unidades_por_mes=total / divisor,
            meses_considerados=divisor,
            total_unidades=total,
        )
