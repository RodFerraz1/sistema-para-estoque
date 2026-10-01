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


def test_carregar_sku_encontra() -> None:
    sku = make_sku("TBC-BEG-70140")
    catalog = Catalog(InMemoryERPAdapter(skus=[sku]))

    encontrado = catalog.carregar_sku("TBC-BEG-70140")

    assert encontrado is not None
    assert encontrado.sku_code == "TBC-BEG-70140"
    assert encontrado.produto_nome == "Produto Teste"
    assert encontrado.categoria == "felpudo"
    assert encontrado.produto_id == uid("produto", "Produto Teste")


def test_carregar_sku_inexistente_retorna_none() -> None:
    catalog = Catalog(InMemoryERPAdapter(skus=[make_sku("A")]))

    assert catalog.carregar_sku("NAO-EXISTE") is None


def test_fornecedores_de_ordenado_por_preco_e_ignora_inativos() -> None:
    sku = make_sku("A")
    caro = make_fornecedor("Caro")
    barato = make_fornecedor("Barato")
    inativo = make_fornecedor("Inativo", ativo=False)

    adapter = InMemoryERPAdapter(
        skus=[sku],
        fornecedores=[caro, barato, inativo],
        fornecedores_por_sku={
            sku.sku_code: [
                make_fornecedor_sku(caro, preco_unitario_reais=5000),
                make_fornecedor_sku(barato, preco_unitario_reais=2000),
                make_fornecedor_sku(inativo, preco_unitario_reais=100),
            ]
        },
    )
    catalog = Catalog(adapter)

    fornecedores = catalog.fornecedores_de("A")

    assert [f.fornecedor_nome for f in fornecedores] == ["Barato", "Caro"]
    assert fornecedores[0].preco_unitario_reais == 2000


def test_fornecedores_de_sku_sem_relacao_retorna_vazio() -> None:
    catalog = Catalog(InMemoryERPAdapter(skus=[make_sku("A")]))

    assert catalog.fornecedores_de("A") == []


def test_listar_skus_devolve_so_os_ativos_por_codigo() -> None:
    catalog = Catalog(
        InMemoryERPAdapter(skus=[make_sku("B"), make_sku("C", ativo=False), make_sku("A")])
    )

    assert [s.sku_code for s in catalog.listar_skus()] == ["A", "B"]
