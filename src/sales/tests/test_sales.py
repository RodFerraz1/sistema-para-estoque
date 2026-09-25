"""Testes unitários do módulo `sales`."""
from __future__ import annotations

from datetime import UTC, datetime

from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.sales.service import Sales
from tests.fakes import make_sku, make_venda


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
# Início do mês corrente (2026-09-01). Últimos 6 meses fechados: mar..ago/2026.


def _sales_at_now(**kwargs) -> Sales:
    adapter = InMemoryERPAdapter(**kwargs)
    return Sales(adapter, now=NOW)


def test_giro_medio_com_seis_meses_cheios() -> None:
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, 3, 10, tzinfo=UTC), 60, key="1"),
        make_venda(sku, datetime(2026, 4, 15, tzinfo=UTC), 60, key="2"),
        make_venda(sku, datetime(2026, 5, 20, tzinfo=UTC), 60, key="3"),
        make_venda(sku, datetime(2026, 6, 5, tzinfo=UTC), 60, key="4"),
        make_venda(sku, datetime(2026, 7, 12, tzinfo=UTC), 60, key="5"),
        make_venda(sku, datetime(2026, 8, 25, tzinfo=UTC), 60, key="6"),
    ]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    giro = sales.giro_medio_mensal(sku.sku_code)

    assert giro.total_unidades == 360
    assert giro.meses_considerados == 6
    assert giro.unidades_por_mes == 60.0


def test_giro_ignora_mes_corrente_parcial() -> None:
    sku = make_sku("A")
    # Vendas anteriores + venda em setembro (mês corrente parcial) devem ficar
    # de fora quando somamos "últimos 6 meses fechados".
    vendas = [
        make_venda(sku, datetime(2026, 3, 10, tzinfo=UTC), 60, key="1"),
        make_venda(sku, datetime(2026, 4, 15, tzinfo=UTC), 60, key="2"),
        make_venda(sku, datetime(2026, 5, 20, tzinfo=UTC), 60, key="3"),
        make_venda(sku, datetime(2026, 6, 5, tzinfo=UTC), 60, key="4"),
        make_venda(sku, datetime(2026, 7, 12, tzinfo=UTC), 60, key="5"),
        make_venda(sku, datetime(2026, 8, 25, tzinfo=UTC), 60, key="6"),
        make_venda(sku, datetime(2026, 9, 10, tzinfo=UTC), 9999, key="setembro"),
    ]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    giro = sales.giro_medio_mensal(sku.sku_code)

    assert giro.total_unidades == 360
    assert giro.unidades_por_mes == 60.0


def test_giro_historico_menor_nao_extrapola() -> None:
    """SKU com apenas 3 meses fechados de histórico usa divisor 3, não 6."""
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, 6, 1, tzinfo=UTC), 30, key="1"),
        make_venda(sku, datetime(2026, 7, 1, tzinfo=UTC), 30, key="2"),
        make_venda(sku, datetime(2026, 8, 1, tzinfo=UTC), 30, key="3"),
    ]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    giro = sales.giro_medio_mensal(sku.sku_code)

    assert giro.total_unidades == 90
    assert giro.meses_considerados == 3
    assert giro.unidades_por_mes == 30.0


def test_giro_sem_vendas_retorna_zero() -> None:
    sku = make_sku("A")
    sales = _sales_at_now(skus=[sku], vendas=[])

    giro = sales.giro_medio_mensal(sku.sku_code)

    assert giro.total_unidades == 0
    assert giro.meses_considerados == 0
    assert giro.unidades_por_mes == 0.0


def test_giro_para_sku_inexistente_retorna_zero() -> None:
    sales = _sales_at_now(skus=[], vendas=[])

    giro = sales.giro_medio_mensal("FANTASMA")

    assert giro.unidades_por_mes == 0.0
    assert giro.meses_considerados == 0


def test_giro_apenas_mes_corrente_sem_meses_fechados() -> None:
    """Vendas só no mês corrente: nenhum mês fechado -> giro 0."""
    sku = make_sku("A")
    vendas = [make_venda(sku, datetime(2026, 9, 10, tzinfo=UTC), 50, key="1")]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    giro = sales.giro_medio_mensal(sku.sku_code)

    assert giro.unidades_por_mes == 0.0
    assert giro.meses_considerados == 0


def test_historico_vendas_retorna_serie_zero_fill() -> None:
    """Série mensal completa (zero-fill) do mais antigo pro mais recente."""
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, 6, 10, tzinfo=UTC), 40, key="jun",
                   valor_unitario_reais=1000),
        make_venda(sku, datetime(2026, 6, 20, tzinfo=UTC), 10, key="jun2",
                   valor_unitario_reais=1000),
        make_venda(sku, datetime(2026, 8, 5, tzinfo=UTC), 20, key="ago",
                   valor_unitario_reais=1500),
    ]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    historico = sales.historico_vendas(sku.sku_code, meses=3)

    assert len(historico) == 3
    assert (historico[0].ano, historico[0].mes) == (2026, 6)
    assert historico[0].quantidade_unidades == 50
    assert historico[0].valor_total_reais == 50 * 1000
    assert (historico[1].ano, historico[1].mes) == (2026, 7)
    assert historico[1].quantidade_unidades == 0
    assert historico[1].valor_total_reais == 0
    assert (historico[2].ano, historico[2].mes) == (2026, 8)
    assert historico[2].quantidade_unidades == 20
    assert historico[2].valor_total_reais == 20 * 1500


def test_historico_vendas_ignora_mes_corrente_parcial() -> None:
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, 8, 15, tzinfo=UTC), 10, key="ago"),
        make_venda(sku, datetime(2026, 9, 10, tzinfo=UTC), 9999, key="set"),
    ]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    historico = sales.historico_vendas(sku.sku_code, meses=2)

    meses = {(h.ano, h.mes) for h in historico}
    assert (2026, 9) not in meses
    assert (2026, 8) in meses


def test_historico_vendas_sku_sem_vendas_retorna_serie_zero() -> None:
    sku = make_sku("A")
    sales = _sales_at_now(skus=[sku], vendas=[])

    historico = sales.historico_vendas(sku.sku_code, meses=3)

    assert len(historico) == 3
    assert all(h.quantidade_unidades == 0 for h in historico)
    assert all(h.valor_total_reais == 0 for h in historico)


def test_historico_vendas_sku_inexistente_retorna_serie_zero() -> None:
    sales = _sales_at_now()

    historico = sales.historico_vendas("FANTASMA", meses=2)

    assert len(historico) == 2
    assert all(h.quantidade_unidades == 0 for h in historico)


def test_sazonalidade_com_pattern_definido() -> None:
    """Vende 100 em jul de 2025+2026 e 50 nos outros meses do período de 24 meses.
    Jul deve ficar acima de 1.0, os outros abaixo."""
    sku = make_sku("A")
    vendas: list = []
    for ano in (2024, 2025, 2026):
        for mes in range(1, 13):
            if ano == 2024 and mes < 9:
                continue
            if ano == 2026 and mes >= 9:
                continue
            qty = 100 if mes == 7 else 50
            vendas.append(
                make_venda(
                    sku, datetime(ano, mes, 15, tzinfo=UTC), qty,
                    key=f"{ano}-{mes:02d}",
                )
            )
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    sazo = sales.sazonalidade(sku.sku_code)

    assert sazo.meses_considerados == 24
    assert len(sazo.multiplicadores) == 12
    assert sazo.multiplicadores[7] > 1.0
    for m in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12):
        assert sazo.multiplicadores[m] < 1.0
    # A soma dos multiplicadores (ponderada pelas ocorrências, 2 cada) / 24
    # deve ser 1.0 (por definição).
    soma_pond = sum(sazo.multiplicadores[m] * 2 for m in range(1, 13))
    assert abs(soma_pond / 24 - 1.0) < 1e-9


def test_sazonalidade_sku_sem_vendas_retorna_neutro() -> None:
    sku = make_sku("A")
    sales = _sales_at_now(skus=[sku], vendas=[])

    sazo = sales.sazonalidade(sku.sku_code)

    assert sazo.meses_considerados == 0
    assert sazo.multiplicadores == {m: 1.0 for m in range(1, 13)}


def test_sazonalidade_sku_inexistente_retorna_neutro() -> None:
    sales = _sales_at_now()

    sazo = sales.sazonalidade("FANTASMA")

    assert sazo.meses_considerados == 0
    assert sazo.multiplicadores == {m: 1.0 for m in range(1, 13)}
