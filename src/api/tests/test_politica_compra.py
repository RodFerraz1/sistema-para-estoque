"""Testes HTTP de `/politica-compra`."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo() -> Iterator[InMemoryPoliticaCompraRepositorio]:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: repo
    yield repo
    app.dependency_overrides.pop(get_politica_compra_repositorio, None)


@pytest.fixture
def client(repo: InMemoryPoliticaCompraRepositorio) -> TestClient:
    return TestClient(app)


def _parametros(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "teto_meses": 3.0,
        "piso_alerta_dias": 15,
        "piso_reposicao_dias": 30,
        "ciclo_compra_meses": 1.0,
        "lead_time_base": "maior",
        "criterio_fornecedor": "menor_lead_time",
        "sazonalidade_modo": "ignorar",
        "meses_quentes": [11, 12],
        "extra_sazonal_meses": 1.0,
        "dias_historico_minimo": 90,
    }
    return base | overrides


def test_get_devolve_a_politica_ativa(client: TestClient) -> None:
    response = client.get("/politica-compra")

    assert response.status_code == 200
    assert response.json() == {
        "versao": 1,
        "criada_em": "2026-09-29T12:00:00Z",
        "parametros": {
            "teto_meses": 3.0,
            "piso_alerta_dias": 20,
            "piso_reposicao_dias": 30,
            "ciclo_compra_meses": 1.0,
            "lead_time_base": "observado",
            "criterio_fornecedor": "menor_preco",
            "sazonalidade_modo": "alertar",
            "meses_quentes": [5, 6, 11, 12],
            "extra_sazonal_meses": 2.0,
            "dias_historico_minimo": 60,
        },
    }


def test_put_grava_versao_nova_e_devolve_201(
    client: TestClient, repo: InMemoryPoliticaCompraRepositorio
) -> None:
    response = client.put("/politica-compra", json=_parametros())

    assert response.status_code == 201
    body = response.json()
    assert body["versao"] == 2
    assert body["parametros"] == _parametros()
    assert client.get("/politica-compra").json() == body
    assert repo.versao(1) is not None


def test_put_invalido_devolve_422_e_nao_grava(
    client: TestClient, repo: InMemoryPoliticaCompraRepositorio
) -> None:
    response = client.put(
        "/politica-compra", json=_parametros(piso_alerta_dias=40, piso_reposicao_dias=30)
    )

    assert response.status_code == 422
    assert repo.ativa().versao == 1


def test_put_incompleto_devolve_422(client: TestClient) -> None:
    parametros = _parametros()
    del parametros["teto_meses"]

    response = client.put("/politica-compra", json=parametros)

    assert response.status_code == 422
