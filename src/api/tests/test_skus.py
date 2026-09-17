"""Testes HTTP do endpoint `/skus/{sku_code}/analise`."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_sku,
    make_venda,
)


def _adapter_completo() -> InMemoryERPAdapter:
    sku = make_sku("TBC-BEG-70140", produto_nome="Toalha Banho", categoria="felpudo")
    outro = make_sku("XPTO-001", produto_nome="Outro", categoria="mesa")

    katrina = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35)
    verdela = make_fornecedor("Verdela Home", lead_time_dias_contratado=60)

    vendas = [
        make_venda(sku, datetime(2026, 3, 5, tzinfo=UTC), 30, key="1"),
        make_venda(sku, datetime(2026, 4, 5, tzinfo=UTC), 30, key="2"),
        make_venda(sku, datetime(2026, 5, 5, tzinfo=UTC), 30, key="3"),
        make_venda(sku, datetime(2026, 6, 5, tzinfo=UTC), 30, key="4"),
        make_venda(sku, datetime(2026, 7, 5, tzinfo=UTC), 30, key="5"),
        make_venda(sku, datetime(2026, 8, 5, tzinfo=UTC), 30, key="6"),
    ]

    return InMemoryERPAdapter(
        skus=[sku, outro],
        fornecedores=[katrina, verdela],
        fornecedores_skus=[
            make_fornecedor_sku(
                sku, katrina, preco_unitario_atual=1800, moq_unidades=48
            ),
            make_fornecedor_sku(
                sku, verdela, preco_unitario_atual=1950, moq_unidades=60
            ),
        ],
        estoques=[make_estoque(sku, disponivel=120, reservada=10)],
        vendas=vendas,
    )


def _client(adapter: InMemoryERPAdapter) -> TestClient:
    app.dependency_overrides[get_erp_adapter] = lambda: adapter
    return TestClient(app)


def _cleanup() -> None:
    app.dependency_overrides.pop(get_erp_adapter, None)


def test_analise_sku_retorna_shape_esperado() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/TBC-BEG-70140/analise")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert body["sku_code"] == "TBC-BEG-70140"
    assert body["produto_nome"] == "Toalha Banho"
    assert body["categoria"] == "felpudo"
    assert body["estoque"]["quantidade_disponivel"] == 120
    assert body["estoque"]["quantidade_reservada"] == 10
    assert body["giro"]["unidades_por_mes"] > 0
    assert body["cobertura"]["sem_giro"] is False
    assert body["cobertura"]["meses"] is not None
    fornecedores = body["fornecedores"]
    assert len(fornecedores) == 2
    assert fornecedores[0]["fornecedor_nome"] == "Katrina Têxtil"
    assert fornecedores[0]["preco_unitario_reais"] == 1800
    assert fornecedores[0]["lead_time_dias_contratado"] == 35
    assert "lead_time_dias_observado" in fornecedores[0]


def test_analise_sku_inexistente_retorna_404() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/NAO-EXISTE/analise")
    finally:
        _cleanup()

    assert response.status_code == 404
    assert "NAO-EXISTE" in response.json()["detail"]


def test_analise_sku_sem_vendas_marca_sem_giro() -> None:
    sku = make_sku("SEM-VENDAS")
    adapter = InMemoryERPAdapter(
        skus=[sku],
        estoques=[make_estoque(sku, disponivel=50)],
    )
    client = _client(adapter)
    try:
        response = client.get("/skus/SEM-VENDAS/analise")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert body["giro"]["unidades_por_mes"] == 0.0
    assert body["cobertura"]["sem_giro"] is True
    assert body["cobertura"]["meses"] is None
    assert body["fornecedores"] == []
