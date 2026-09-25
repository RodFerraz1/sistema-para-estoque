"""Testes dos métodos de domínio do `InMemoryERPAdapter`.

Espelham as garantias do `PostgresERPAdapter`: mesma chave (`sku_code`),
mesmo filtro de ativos e mesma ordenação.
"""
from __future__ import annotations

from datetime import UTC, datetime

from src.erp_adapter.in_memory import InMemoryERPAdapter
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_movimentacao,
    make_sku,
    make_venda,
    uid,
)


def test_carregar_sku_por_codigo() -> None:
    sku = make_sku("TBC-001", produto_nome="Toalha", categoria="felpudo")
    erp = InMemoryERPAdapter(skus=[sku, make_sku("TBC-002")])

    carregado = erp.carregar_sku("TBC-001")

    assert carregado is not None
    assert carregado.id == sku.id
    assert carregado.produto_id == sku.produto_id
    assert carregado.sku_code == "TBC-001"
    assert carregado.produto_nome == "Toalha"
    assert carregado.categoria == "felpudo"


def test_carregar_sku_inexistente() -> None:
    erp = InMemoryERPAdapter(skus=[make_sku("TBC-001")])

    assert erp.carregar_sku("NAO-EXISTE") is None


def test_listar_skus_ordena_por_codigo() -> None:
    erp = InMemoryERPAdapter(skus=[make_sku("B-002"), make_sku("A-001")])

    skus = erp.listar_skus()

    assert [s.sku_code for s in skus] == ["A-001", "B-002"]


def test_listar_skus_corta_inativos() -> None:
    erp = InMemoryERPAdapter(
        skus=[make_sku("A-001"), make_sku("B-002", ativo=False)]
    )

    assert [s.sku_code for s in erp.listar_skus()] == ["A-001"]


def test_listar_skus_vazio() -> None:
    assert InMemoryERPAdapter().listar_skus() == []


def test_carregar_fornecedor() -> None:
    fornecedor = make_fornecedor("Katrina Têxtil")
    erp = InMemoryERPAdapter(fornecedores=[fornecedor])

    carregado = erp.carregar_fornecedor(fornecedor.id)

    assert carregado is not None
    assert carregado.nome == "Katrina Têxtil"
    assert carregado.cnpj == fornecedor.cnpj


def test_carregar_fornecedor_inexistente() -> None:
    erp = InMemoryERPAdapter(fornecedores=[make_fornecedor()])

    assert erp.carregar_fornecedor(uid("fornecedor", "fantasma")) is None


def test_fornecedores_de_ordena_por_preco() -> None:
    sku = make_sku("TBC-001")
    caro = make_fornecedor("Caro")
    barato = make_fornecedor("Barato")
    erp = InMemoryERPAdapter(
        skus=[sku],
        fornecedores=[caro, barato],
        fornecedores_skus=[
            make_fornecedor_sku(sku, caro, preco_unitario_atual=3000),
            make_fornecedor_sku(sku, barato, preco_unitario_atual=1500),
        ],
    )

    fornecedores = erp.fornecedores_de("TBC-001")

    assert [f.fornecedor_nome for f in fornecedores] == ["Barato", "Caro"]
    assert [f.preco_unitario_reais for f in fornecedores] == [1500, 3000]


def test_fornecedores_de_corta_inativos() -> None:
    sku = make_sku("TBC-001")
    ativo = make_fornecedor("Ativo")
    fornecedor_inativo = make_fornecedor("Fornecedor Inativo", ativo=False)
    vinculo_inativo = make_fornecedor("Vínculo Inativo")
    erp = InMemoryERPAdapter(
        skus=[sku],
        fornecedores=[ativo, fornecedor_inativo, vinculo_inativo],
        fornecedores_skus=[
            make_fornecedor_sku(sku, ativo),
            make_fornecedor_sku(sku, fornecedor_inativo),
            make_fornecedor_sku(sku, vinculo_inativo, ativo=False),
        ],
    )

    fornecedores = erp.fornecedores_de("TBC-001")

    assert [f.fornecedor_nome for f in fornecedores] == ["Ativo"]


def test_fornecedores_de_sku_inexistente() -> None:
    assert InMemoryERPAdapter().fornecedores_de("NAO-EXISTE") == []


def test_fornecedores_de_sku_sem_fornecedores() -> None:
    erp = InMemoryERPAdapter(skus=[make_sku("TBC-001")])

    assert erp.fornecedores_de("TBC-001") == []


def test_estoque_de() -> None:
    sku = make_sku("TBC-001")
    erp = InMemoryERPAdapter(
        skus=[sku], estoques=[make_estoque(sku, disponivel=42, reservada=3)]
    )

    estoque = erp.estoque_de("TBC-001")

    assert estoque is not None
    assert estoque.quantidade_disponivel == 42
    assert estoque.quantidade_reservada == 3


def test_estoque_de_sku_inexistente() -> None:
    assert InMemoryERPAdapter().estoque_de("NAO-EXISTE") is None


def test_estoque_de_sku_sem_snapshot() -> None:
    erp = InMemoryERPAdapter(skus=[make_sku("TBC-001")])

    assert erp.estoque_de("TBC-001") is None


def test_vendas_de_filtra_por_sku_e_data_e_ordena() -> None:
    sku = make_sku("TBC-001")
    outro = make_sku("TBC-002")
    erp = InMemoryERPAdapter(
        skus=[sku, outro],
        vendas=[
            make_venda(sku, datetime(2026, 3, 1, tzinfo=UTC), 5),
            make_venda(sku, datetime(2026, 1, 1, tzinfo=UTC), 7),
            make_venda(sku, datetime(2025, 12, 1, tzinfo=UTC), 9),
            make_venda(outro, datetime(2026, 2, 1, tzinfo=UTC), 11),
        ],
    )

    vendas = erp.vendas_de("TBC-001", datetime(2026, 1, 1, tzinfo=UTC))

    assert [v.quantidade for v in vendas] == [7, 5]
    assert all(v.sku_id == sku.id for v in vendas)


def test_vendas_de_sku_inexistente() -> None:
    erp = InMemoryERPAdapter()

    assert erp.vendas_de("NAO-EXISTE", datetime(2020, 1, 1, tzinfo=UTC)) == []


def test_movimentacoes_de_filtra_por_sku_e_data_e_ordena() -> None:
    sku = make_sku("TBC-001")
    outro = make_sku("TBC-002")
    erp = InMemoryERPAdapter(
        skus=[sku, outro],
        movimentacoes=[
            make_movimentacao(sku, datetime(2026, 3, 1, tzinfo=UTC), "saida_venda", 5),
            make_movimentacao(
                sku, datetime(2026, 1, 1, tzinfo=UTC), "entrada_compra", 100
            ),
            make_movimentacao(
                sku, datetime(2025, 12, 1, tzinfo=UTC), "entrada_compra", 50
            ),
            make_movimentacao(
                outro, datetime(2026, 2, 1, tzinfo=UTC), "saida_venda", 1
            ),
        ],
    )

    movs = erp.movimentacoes_de("TBC-001", datetime(2026, 1, 1, tzinfo=UTC))

    assert [(m.tipo, m.quantidade) for m in movs] == [
        ("entrada_compra", 100),
        ("saida_venda", 5),
    ]
    assert all(m.sku_id == sku.id for m in movs)


def test_movimentacoes_de_sku_inexistente() -> None:
    erp = InMemoryERPAdapter()

    assert erp.movimentacoes_de("NAO-EXISTE", datetime(2020, 1, 1, tzinfo=UTC)) == []
