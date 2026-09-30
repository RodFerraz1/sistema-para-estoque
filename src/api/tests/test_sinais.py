"""Testes HTTP de `/skus/{sku_code}/sugestao-compra/sinais` com ERP, política, busca e
Jev em memória."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.ai.dependencies import get_decision_model, get_embedder, get_trechos_repositorio
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel
from src.api.schemas import SinalCorpusResponse
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_sku,
    make_trecho,
    make_venda,
    repositorio_com,
)

PRECISA_COMPRAR = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", categoria="felpudo")
SEM_COMPRA = make_sku("TBC-BRAN-70140-03", produto_nome="Toalha Banho Conforto", categoria="felpudo")
REVISAO_Q1 = "reunioes/2025-q1-revisao-fornecedores.md#katrina-textil"
DEPENDENCIAS = (
    get_erp_adapter,
    get_politica_compra_repositorio,
    get_embedder,
    get_trechos_repositorio,
    get_decision_model,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def preparar(decisao: InMemoryDecisionModel | None = None) -> None:
    """Giro de 100 por mês: o SKU que precisa comprar tem 150 disponíveis e compra da
    Katrina; o outro tem 900 e fica sem compra, sem fornecedor. Sem `decisao`, o Jev
    fica o de verdade, que falha sem `JEV_KEY`."""
    katrina = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35)
    adapter = InMemoryERPAdapter(
        skus=[PRECISA_COMPRAR, SEM_COMPRA],
        fornecedores=[katrina],
        fornecedores_por_sku={
            sku.sku_code: [make_fornecedor_sku(katrina, lead_time_dias_observado=62)]
            for sku in (PRECISA_COMPRAR, SEM_COMPRA)
        },
        estoques={
            PRECISA_COMPRAR.sku_code: make_estoque(disponivel=150),
            SEM_COMPRA.sku_code: make_estoque(disponivel=900),
        },
        vendas=[
            make_venda(sku, datetime(2026, mes, 5, tzinfo=UTC), 100, key=f"{sku.sku_code}-{mes}")
            for sku in (PRECISA_COMPRAR, SEM_COMPRA)
            for mes in range(3, 9)
        ],
    )
    embedder = FakeEmbedder()
    trechos = repositorio_com([make_trecho(REVISAO_Q1, "Katrina Têxtil atrasou de novo")], embedder)
    politicas = InMemoryPoliticaCompraRepositorio()
    app.dependency_overrides[get_erp_adapter] = lambda: adapter
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: politicas
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_trechos_repositorio] = lambda: trechos
    if decisao is not None:
        app.dependency_overrides[get_decision_model] = lambda: decisao


def jev(**kwargs) -> InMemoryDecisionModel:
    return InMemoryDecisionModel(
        padrao={"relevante": 0.9, "tem_evidencia": 0.9},
        sinais={REVISAO_Q1: {"atraso_do_fornecedor": 0.98}},
        **kwargs,
    )


def test_sinais_da_sugestao_com_os_trechos_de_origem(client: TestClient) -> None:
    preparar(jev())

    response = client.get(f"/skus/{PRECISA_COMPRAR.sku_code}/sugestao-compra/sinais")

    assert response.status_code == 200
    assert [SinalCorpusResponse.model_validate(s) for s in response.json()] == [
        SinalCorpusResponse(
            tipo="atraso_do_fornecedor",
            mensagem="Os documentos relatam atraso de entrega da Katrina Têxtil.",
            trechos=[REVISAO_Q1],
            probabilidade=0.98,
        )
    ]


def test_sugestao_sem_fornecedor_devolve_lista_vazia(client: TestClient) -> None:
    preparar(jev(falhar_trechos=True, falhar_sinais=True))

    response = client.get(f"/skus/{SEM_COMPRA.sku_code}/sugestao-compra/sinais")

    assert response.status_code == 200
    assert response.json() == []


def test_sku_inexistente_da_404(client: TestClient) -> None:
    preparar(jev())

    response = client.get("/skus/NAO-EXISTE/sugestao-compra/sinais")

    assert response.status_code == 404
    assert "NAO-EXISTE" in response.json()["detail"]


def test_jev_indisponivel_da_503(client: TestClient) -> None:
    preparar(jev(falhar_sinais=True))

    response = client.get(f"/skus/{PRECISA_COMPRAR.sku_code}/sugestao-compra/sinais")

    assert response.status_code == 503
    assert response.json()["detail"]


def test_sem_jev_key_da_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_KEY", "")
    preparar()

    response = client.get(f"/skus/{PRECISA_COMPRAR.sku_code}/sugestao-compra/sinais")

    assert response.status_code == 503
