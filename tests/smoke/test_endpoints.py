"""Smoke test end-to-end: valida o contrato de cada endpoint público.

Executa contra o Postgres real com o seed populado. Não faz asserções
sobre valores exatos (que variam com a data de execução do seed) - só
sobre status code e shape, via os DTOs Pydantic da camada API. Serve de
regression net pros próximos specs.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.schemas import (
    AnaliseSKUResponse,
    FornecedorResponse,
    SKUAbaixoDoPisoResponse,
    VendaMensalResponse,
)

pytestmark = pytest.mark.smoke


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_analise_sku_shape(client: TestClient, sku_code: str) -> None:
    response = client.get(f"/skus/{sku_code}/analise")
    assert response.status_code == 200
    analise = AnaliseSKUResponse.model_validate(response.json())
    assert analise.sku_code == sku_code
    assert analise.produto_nome
    assert analise.categoria in {"felpudo", "jogo_cama", "mesa", "cozinha"}
    assert analise.estoque.quantidade_disponivel >= 0
    assert analise.giro.meses_considerados >= 0
    assert analise.giro.unidades_por_mes >= 0


def test_analise_sku_inexistente_404(client: TestClient) -> None:
    response = client.get("/skus/NAO-EXISTE-999/analise")
    assert response.status_code == 404


def test_abaixo_do_piso_shape(client: TestClient) -> None:
    response = client.get("/skus/abaixo-do-piso")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for entry in body:
        item = SKUAbaixoDoPisoResponse.model_validate(entry)
        assert item.cobertura_meses >= 0


def test_abaixo_do_piso_com_parametro(client: TestClient) -> None:
    response = client.get("/skus/abaixo-do-piso", params={"dias": 60})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_vendas_shape(client: TestClient, sku_code: str) -> None:
    response = client.get(f"/skus/{sku_code}/vendas", params={"meses": 12})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 12
    for entry in body:
        venda = VendaMensalResponse.model_validate(entry)
        assert 1 <= venda.mes <= 12
        assert venda.quantidade_unidades >= 0


def test_sazonalidade_shape(client: TestClient, sku_code: str) -> None:
    response = client.get(f"/skus/{sku_code}/sazonalidade")
    assert response.status_code == 200
    body = response.json()
    assert {int(k) for k in body.keys()} == set(range(1, 13))
    for value in body.values():
        assert isinstance(value, (int, float))
        assert value >= 0


def test_fornecedores_shape(client: TestClient, sku_code: str) -> None:
    response = client.get(f"/skus/{sku_code}/fornecedores")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for entry in body:
        fornecedor = FornecedorResponse.model_validate(entry)
        assert fornecedor.fornecedor_nome
        assert fornecedor.preco_unitario_reais > 0
        assert fornecedor.moq_unidades > 0
        assert fornecedor.lead_time_dias_contratado > 0
