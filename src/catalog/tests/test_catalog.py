"""Testes unitários do módulo `catalog` usando `InMemoryERPAdapter`."""
from __future__ import annotations

from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from tests.fakes import (
    make_fornecedor,
    make_fornecedor_sku,
    make_sku,
    uid,
)


def test_buscar_sku_por_codigo_encontra() -> None:
    sku = make_sku("TBC-BEG-70140")
    catalog = Catalog(InMemoryERPAdapter(skus=[sku]))

    encontrado = catalog.buscar_sku_por_codigo("TBC-BEG-70140")

    assert encontrado is not None
    assert encontrado.sku_code == "TBC-BEG-70140"
    assert encontrado.produto_nome == "Produto Teste"
    assert encontrado.categoria == "felpudo"
    assert encontrado.produto_id == uid("produto", "Produto Teste")


def test_buscar_sku_por_codigo_inexistente_retorna_none() -> None:
    catalog = Catalog(InMemoryERPAdapter(skus=[make_sku("A")]))

    assert catalog.buscar_sku_por_codigo("NAO-EXISTE") is None


def test_get_sku_por_id() -> None:
    sku = make_sku("A")
    catalog = Catalog(InMemoryERPAdapter(skus=[sku]))

    assert catalog.get_sku(sku.id) is not None
    assert catalog.get_sku(uid("sku", "fantasma")) is None


def test_list_fornecedores_ordenado_por_preco_e_ignora_inativos() -> None:
    sku = make_sku("A")
    caro = make_fornecedor("Caro")
    barato = make_fornecedor("Barato")
    inativo = make_fornecedor("Inativo", ativo=False)

    adapter = InMemoryERPAdapter(
        skus=[sku],
        fornecedores=[caro, barato, inativo],
        fornecedores_skus=[
            make_fornecedor_sku(sku, caro, preco_unitario_atual=5000),
            make_fornecedor_sku(sku, barato, preco_unitario_atual=2000),
            make_fornecedor_sku(sku, inativo, preco_unitario_atual=100),
        ],
    )
    catalog = Catalog(adapter)

    fornecedores = catalog.list_fornecedores_para_sku(sku.id)

    assert [f.fornecedor_nome for f in fornecedores] == ["Barato", "Caro"]
    assert fornecedores[0].preco_unitario_reais == 2000


def test_list_fornecedores_sku_sem_relacao_retorna_vazio() -> None:
    catalog = Catalog(InMemoryERPAdapter(skus=[make_sku("A")]))

    assert catalog.list_fornecedores_para_sku(uid("sku", "A")) == []
