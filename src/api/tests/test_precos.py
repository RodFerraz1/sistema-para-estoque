"""Testes HTTP de `/skus/{sku}/precos` com ERP em memória.

`TOALHA` (felpudo, 70x140) tem dois fornecedores e três pedidos de compra, um deles
cancelado. Os substitutos candidatos são da mesma categoria e tamanho, de outro produto.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.catalog.schemas import SKU, Fornecedor
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter, ItemPedidoCompra, PedidoCompra
from src.erp_adapter.schemas import StatusPedidoCompra
from src.main import app
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
)

KATRINA = make_fornecedor("Katrina Têxtil")
BOA_VISTA = make_fornecedor("Boa Vista Têxtil")
TOALHA = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege")
MESMO_PRODUTO = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto", cor="branco")
OUTRO_TAMANHO = make_sku("TBP-BEGE-90150-01", produto_nome="Toalha Banho Premium", tamanho="90x150")
OUTRA_CATEGORIA = make_sku("PM-BEGE-70140-01", produto_nome="Pano de Mesa", categoria="mesa")
SEM_FORNECEDOR = make_sku("TBS-BEGE-70140-01", produto_nome="Toalha Banho Simples")
INATIVO = make_sku("TBV-BEGE-70140-01", produto_nome="Toalha Banho Velha", ativo=False)
SUBSTITUTO_BARATO = make_sku("TBL-AZUL-70140-01", produto_nome="Toalha Banho Leve", cor="azul")
SUBSTITUTO_CARO = make_sku("TBG-VERD-70140-01", produto_nome="Toalha Banho Grossa", cor="verde")


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.pop(get_erp_adapter, None)


def _pedido(
    status: StatusPedidoCompra, mes: int, preco: int, fornecedor: Fornecedor = KATRINA
) -> tuple[PedidoCompra, ItemPedidoCompra]:
    pedido = make_pedido_compra(fornecedor, status, key=f"{status}-{mes}", criado_em=datetime(2026, mes, 10, tzinfo=UTC))
    return pedido, make_item_pedido_compra(pedido, TOALHA, quantidade=48 * mes, preco_unitario_centavos=preco)


def preparar(*, skus: list[SKU] | None = None, precos_substitutos: dict[str, list[int]] | None = None) -> None:
    pedidos = [
        _pedido("recebido_total", 3, 1700),
        _pedido("cancelado", 6, 1500),
        _pedido("enviado", 8, 1850, BOA_VISTA),
    ]
    precos_substitutos = precos_substitutos or {
        SUBSTITUTO_BARATO.sku_code: [1900, 1600],
        SUBSTITUTO_CARO.sku_code: [2500],
        OUTRO_TAMANHO.sku_code: [100],
        OUTRA_CATEGORIA.sku_code: [100],
        MESMO_PRODUTO.sku_code: [100],
        INATIVO.sku_code: [100],
    }
    fornecedores = [KATRINA, BOA_VISTA]
    por_sku = {
        TOALHA.sku_code: [
            make_fornecedor_sku(KATRINA, preco_unitario_reais=1800),
            make_fornecedor_sku(BOA_VISTA, preco_unitario_reais=1950),
        ],
        **{
            code: [
                make_fornecedor_sku(fornecedores[i % 2], preco_unitario_reais=preco)
                for i, preco in enumerate(precos)
            ]
            for code, precos in precos_substitutos.items()
        },
    }
    todos = [TOALHA, MESMO_PRODUTO, OUTRO_TAMANHO, OUTRA_CATEGORIA, SEM_FORNECEDOR, INATIVO, SUBSTITUTO_BARATO]
    erp = InMemoryERPAdapter(
        skus=skus or [*todos, SUBSTITUTO_CARO],
        fornecedores=fornecedores,
        fornecedores_por_sku={code: sorted(f, key=lambda f: f.preco_unitario_reais) for code, f in por_sku.items()},
        estoques={TOALHA.sku_code: make_estoque(disponivel=100)},
        pedidos_compra=[p for p, _ in pedidos],
        itens_pedido_compra=[i for _, i in pedidos],
    )
    app.dependency_overrides[get_erp_adapter] = lambda: erp


def precos(client: TestClient, sku: SKU = TOALHA) -> dict:
    response = client.get(f"/skus/{sku.sku_code}/precos")
    assert response.status_code == 200
    return response.json()


def test_historico_vem_do_mais_recente_para_o_mais_antigo_sem_cancelado(client: TestClient) -> None:
    preparar()

    historico = precos(client)["historico"]

    assert historico == [
        {
            "data": "2026-08-10T00:00:00Z",
            "fornecedor_nome": "Boa Vista Têxtil",
            "preco_unitario_centavos": 1850,
            "quantidade": 384,
            "status": "enviado",
        },
        {
            "data": "2026-03-10T00:00:00Z",
            "fornecedor_nome": "Katrina Têxtil",
            "preco_unitario_centavos": 1700,
            "quantidade": 144,
            "status": "recebido_total",
        },
    ]


def test_precos_atuais_trazem_cada_fornecedor_do_mais_barato_ao_mais_caro(client: TestClient) -> None:
    preparar()

    atuais = precos(client)["precos_atuais"]

    assert [(f["fornecedor_nome"], f["preco_unitario_reais"]) for f in atuais] == [
        ("Katrina Têxtil", 1800),
        ("Boa Vista Têxtil", 1950),
    ]


def test_substitutos_sao_outro_produto_ativo_da_mesma_categoria_e_tamanho_pelo_menor_preco(
    client: TestClient,
) -> None:
    preparar()

    substitutos = precos(client)["substitutos"]

    assert substitutos == [
        {
            "sku_code": SUBSTITUTO_BARATO.sku_code,
            "produto_nome": "Toalha Banho Leve",
            "cor": "azul",
            "tamanho": "70x140",
            "preco_unitario_centavos": 1600,
            "fornecedor_nome": "Boa Vista Têxtil",
        },
        {
            "sku_code": SUBSTITUTO_CARO.sku_code,
            "produto_nome": "Toalha Banho Grossa",
            "cor": "verde",
            "tamanho": "70x140",
            "preco_unitario_centavos": 2500,
            "fornecedor_nome": "Katrina Têxtil",
        },
    ]


def test_substitutos_param_em_10(client: TestClient) -> None:
    muitos = [make_sku(f"TBX-{i:02d}-70140", produto_nome=f"Toalha Banho {i:02d}") for i in range(12)]
    preparar(
        skus=[TOALHA, *muitos],
        precos_substitutos={sku.sku_code: [3000 - i * 100] for i, sku in enumerate(muitos)},
    )

    substitutos = precos(client)["substitutos"]

    assert [s["preco_unitario_centavos"] for s in substitutos] == [3000 - i * 100 for i in range(11, 1, -1)]


def test_sku_sem_pedido_nem_substituto_responde_listas_vazias(client: TestClient) -> None:
    preparar(skus=[SEM_FORNECEDOR], precos_substitutos={})

    resposta = precos(client, SEM_FORNECEDOR)

    assert resposta == {"historico": [], "precos_atuais": [], "substitutos": []}


def test_sku_inexistente_responde_404(client: TestClient) -> None:
    preparar()

    response = client.get("/skus/NAO-EXISTE/precos")

    assert response.status_code == 404
    assert "NAO-EXISTE" in response.json()["detail"]
