"""Testes unitários do módulo `inventory`."""
from __future__ import annotations

from datetime import UTC, datetime

from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.inventory.service import Inventory
from src.sales.service import Sales
from tests.fakes import make_estoque, make_sku, make_venda, uid


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _inv(**kwargs) -> Inventory:
    adapter = InMemoryERPAdapter(**kwargs)
    return Inventory(adapter, Sales(adapter, now=NOW))


def test_estoque_atual_retorna_dto() -> None:
    sku = make_sku("A")
    inv = _inv(skus=[sku], estoques=[make_estoque(sku, disponivel=200, reservada=15)])

    estoque = inv.estoque_atual(sku.id)

    assert estoque is not None
    assert estoque.quantidade_disponivel == 200
    assert estoque.quantidade_reservada == 15


def test_estoque_atual_inexistente_retorna_none() -> None:
    inv = _inv()

    assert inv.estoque_atual(uid("sku", "fantasma")) is None


def test_cobertura_calcula_meses() -> None:
    sku = make_sku("A")
    # 6 vendas de 60 unidades em meses fechados diferentes -> giro 60/mês.
    vendas = [
        make_venda(sku, datetime(2026, 3, 10, tzinfo=UTC), 60, key="1"),
        make_venda(sku, datetime(2026, 4, 10, tzinfo=UTC), 60, key="2"),
        make_venda(sku, datetime(2026, 5, 10, tzinfo=UTC), 60, key="3"),
        make_venda(sku, datetime(2026, 6, 10, tzinfo=UTC), 60, key="4"),
        make_venda(sku, datetime(2026, 7, 10, tzinfo=UTC), 60, key="5"),
        make_venda(sku, datetime(2026, 8, 10, tzinfo=UTC), 60, key="6"),
    ]
    inv = _inv(
        skus=[sku],
        estoques=[make_estoque(sku, disponivel=120, reservada=0)],
        vendas=vendas,
    )

    cobertura = inv.cobertura_meses(sku.id)

    assert cobertura.sem_giro is False
    assert cobertura.meses == 2.0


def test_cobertura_sem_giro_quando_giro_zero() -> None:
    """SKU com estoque mas sem vendas: sem_giro=True, meses=None."""
    sku = make_sku("A")
    inv = _inv(
        skus=[sku],
        estoques=[make_estoque(sku, disponivel=50)],
        vendas=[],
    )

    cobertura = inv.cobertura_meses(sku.id)

    assert cobertura.sem_giro is True
    assert cobertura.meses is None


def test_cobertura_zero_quando_estoque_zero_e_ha_giro() -> None:
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, m, 10, tzinfo=UTC), 60, key=str(m))
        for m in range(3, 9)
    ]
    inv = _inv(
        skus=[sku],
        estoques=[make_estoque(sku, disponivel=0)],
        vendas=vendas,
    )

    cobertura = inv.cobertura_meses(sku.id)

    assert cobertura.sem_giro is False
    assert cobertura.meses == 0.0
