"""Módulo `sales`: sabe sobre venda, giro, sazonalidade."""
from __future__ import annotations

from datetime import UTC, datetime

from src.erp_adapter.port import ERPAdapter
from src.sales.schemas import GiroMedioMensal, Sazonalidade, Venda, VendaMensal

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


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month + months
    year = dt.year
    while month > 12:
        month -= 12
        year += 1
    return dt.replace(year=year, month=month)


def _months_between(inicio: datetime, fim: datetime) -> int:
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


class Sales:
    def __init__(self, erp: ERPAdapter, *, now: datetime | None = None) -> None:
        self._erp = erp
        self._now = now

    def _agora(self) -> datetime:
        return self._now or datetime.now(UTC)

    def _vendas_fechadas(
        self, sku_code: str, meses: int
    ) -> tuple[list[Venda], datetime, datetime]:
        """Vendas na janela de `meses` fechados antes do mês corrente.

        Retorna `(vendas, janela_inicio, fim)` onde `fim` é o início do mês
        corrente (exclusivo) e `janela_inicio` é `fim - meses` (inclusivo).
        """
        fim = _start_of_month(self._agora())
        janela_inicio = _subtract_months(fim, meses)
        todas = self._erp.vendas_de(sku_code, janela_inicio)
        return [v for v in todas if v.data < fim], janela_inicio, fim

    def giro_medio_mensal(self, sku_code: str, meses: int = 6) -> GiroMedioMensal:
        fim = _start_of_month(self._agora())
        janela_inicio = _subtract_months(fim, meses)

        todas = self._erp.vendas_de(sku_code, _EPOCH)
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

    def primeira_venda(self, sku_code: str) -> datetime | None:
        """Data da venda mais antiga do SKU, ou `None` se nunca vendeu."""
        vendas = self._erp.vendas_de(sku_code, _EPOCH)
        return min((v.data for v in vendas), default=None)

    def historico_vendas(
        self, sku_code: str, meses: int = 12
    ) -> list[VendaMensal]:
        """Série mensal (zero-fill) dos últimos `meses` meses fechados.

        Ordenada do mais antigo pro mais recente. Meses sem venda entram
        com quantidade e valor zero pra preservar a forma do sinal.
        """
        fechadas, janela_inicio, fim = self._vendas_fechadas(sku_code, meses)

        buckets: dict[tuple[int, int], tuple[int, int]] = {}
        cursor = janela_inicio
        while cursor < fim:
            buckets[(cursor.year, cursor.month)] = (0, 0)
            cursor = _add_months(cursor, 1)

        for v in fechadas:
            chave = (v.data.year, v.data.month)
            qty, valor = buckets[chave]
            buckets[chave] = (
                qty + v.quantidade,
                valor + v.quantidade * v.valor_unitario_reais,
            )

        return [
            VendaMensal(
                ano=ano,
                mes=mes,
                quantidade_unidades=qty,
                valor_total_reais=valor,
            )
            for (ano, mes), (qty, valor) in sorted(buckets.items())
        ]

    def sazonalidade(self, sku_code: str, meses: int = 24) -> Sazonalidade:
        """Multiplicadores mês-a-mês normalizados pela média do período.

        Para cada mês do ano (1-12) calcula a média de vendas naquele mês
        dentro da janela dividida pela média geral do período. Sem vendas
        na janela retorna multiplicadores neutros (1.0) e
        `meses_considerados=0` como sinal de "sem dado".
        """
        fechadas, janela_inicio, fim = self._vendas_fechadas(sku_code, meses)

        neutro = {m: 1.0 for m in range(1, 13)}
        if not fechadas:
            return Sazonalidade(multiplicadores=neutro, meses_considerados=0)

        ocorrencias: dict[int, int] = {m: 0 for m in range(1, 13)}
        cursor = janela_inicio
        n_meses = 0
        while cursor < fim:
            ocorrencias[cursor.month] += 1
            cursor = _add_months(cursor, 1)
            n_meses += 1

        total_por_mes: dict[int, int] = {m: 0 for m in range(1, 13)}
        for v in fechadas:
            total_por_mes[v.data.month] += v.quantidade

        total = sum(total_por_mes.values())
        if total == 0 or n_meses == 0:
            return Sazonalidade(multiplicadores=neutro, meses_considerados=n_meses)

        overall_avg = total / n_meses
        multiplicadores: dict[int, float] = {}
        for m in range(1, 13):
            if ocorrencias[m] == 0:
                multiplicadores[m] = 1.0
            else:
                multiplicadores[m] = (total_por_mes[m] / ocorrencias[m]) / overall_avg
        return Sazonalidade(
            multiplicadores=multiplicadores, meses_considerados=n_meses
        )
