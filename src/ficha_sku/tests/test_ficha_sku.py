"""Testes unitários do módulo `ficha_sku`."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU, SKUSemEstoque
from src.inventory.service import Inventory
from src.sales.service import Sales
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _ficha_sku(**kwargs) -> FichaSKU:
    adapter = InMemoryERPAdapter(**kwargs)
    sales = Sales(adapter, now=NOW)
    return FichaSKU(Catalog(adapter), Inventory(adapter, sales), sales)


def test_completa_compoe_sku_estoque_giro_cobertura_e_fornecedores() -> None:
    sku = make_sku("A", produto_nome="Toalha Banho")
    katrina = make_fornecedor("Katrina Têxtil")
    verdela = make_fornecedor("Verdela Home")
    vendas = [
        make_venda(sku, datetime(2026, m, 5, tzinfo=UTC), 30, key=str(m))
        for m in range(3, 9)
    ]
    ficha_sku = _ficha_sku(
        skus=[sku],
        fornecedores=[katrina, verdela],
        fornecedores_por_sku={
            sku.sku_code: [
                make_fornecedor_sku(verdela, preco_unitario_reais=1950),
                make_fornecedor_sku(katrina, preco_unitario_reais=1800),
            ]
        },
        estoques={sku.sku_code: make_estoque(disponivel=120, reservada=10)},
        vendas=vendas,
    )

    ficha = ficha_sku.completa("A")

    assert ficha is not None
    assert ficha.sku == sku
    assert ficha.estoque.quantidade_disponivel == 120
    assert ficha.estoque.quantidade_reservada == 10
    assert ficha.em_transito == 0
    assert ficha.giro.unidades_por_mes == 30.0
    assert ficha.giro.meses_considerados == 6
    assert ficha.cobertura.meses == pytest.approx(4.0)
    assert ficha.cobertura.sem_giro is False
    assert [f.fornecedor_nome for f in ficha.fornecedores] == [
        "Katrina Têxtil",
        "Verdela Home",
    ]


def test_completa_sku_inexistente_retorna_none() -> None:
    ficha_sku = _ficha_sku(skus=[make_sku("A")])

    assert ficha_sku.completa("NAO-EXISTE") is None


def test_completa_sku_sem_vendas_marca_sem_giro() -> None:
    sku = make_sku("SEM-VENDAS")
    ficha_sku = _ficha_sku(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=50)},
    )

    ficha = ficha_sku.completa("SEM-VENDAS")

    assert ficha is not None
    assert ficha.giro.unidades_por_mes == 0.0
    assert ficha.cobertura.sem_giro is True
    assert ficha.cobertura.meses is None
    assert ficha.fornecedores == []


def test_completa_sku_sem_snapshot_de_estoque_levanta() -> None:
    ficha_sku = _ficha_sku(skus=[make_sku("A")])

    with pytest.raises(SKUSemEstoque):
        ficha_sku.completa("A")


def test_completa_soma_o_que_falta_chegar_dos_pedidos_abertos() -> None:
    sku = make_sku("A")
    katrina = make_fornecedor("Katrina Têxtil")
    enviado = make_pedido_compra(katrina, "enviado")
    parcial = make_pedido_compra(katrina, "recebido_parcial")
    ficha_sku = _ficha_sku(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=50)},
        pedidos_compra=[enviado, parcial],
        itens_pedido_compra=[
            make_item_pedido_compra(enviado, sku, quantidade=100),
            make_item_pedido_compra(parcial, sku, quantidade=60, quantidade_recebida=20),
        ],
    )

    ficha = ficha_sku.completa("A")

    assert ficha is not None
    assert ficha.em_transito == 140
