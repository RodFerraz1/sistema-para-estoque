"""Testes unitários do módulo `sales`."""
from __future__ import annotations

from datetime import UTC, datetime

from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.sales.service import Sales
from tests.fakes import make_sku, make_venda, uid


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

    giro = sales.giro_medio_mensal(sku.id)

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

    giro = sales.giro_medio_mensal(sku.id)

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

    giro = sales.giro_medio_mensal(sku.id)

    assert giro.total_unidades == 90
    assert giro.meses_considerados == 3
    assert giro.unidades_por_mes == 30.0


def test_giro_sem_vendas_retorna_zero() -> None:
    sku = make_sku("A")
    sales = _sales_at_now(skus=[sku], vendas=[])

    giro = sales.giro_medio_mensal(sku.id)

    assert giro.total_unidades == 0
    assert giro.meses_considerados == 0
    assert giro.unidades_por_mes == 0.0


def test_giro_para_sku_inexistente_retorna_zero() -> None:
    sales = _sales_at_now(skus=[], vendas=[])

    giro = sales.giro_medio_mensal(uid("sku", "fantasma"))

    assert giro.unidades_por_mes == 0.0
    assert giro.meses_considerados == 0


def test_giro_apenas_mes_corrente_sem_meses_fechados() -> None:
    """Vendas só no mês corrente: nenhum mês fechado -> giro 0."""
    sku = make_sku("A")
    vendas = [make_venda(sku, datetime(2026, 9, 10, tzinfo=UTC), 50, key="1")]
    sales = _sales_at_now(skus=[sku], vendas=vendas)

    giro = sales.giro_medio_mensal(sku.id)

    assert giro.unidades_por_mes == 0.0
    assert giro.meses_considerados == 0
