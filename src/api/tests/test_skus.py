"""Testes HTTP do endpoint `/skus/{sku_code}/analise`."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1
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
        fornecedores_por_sku={
            sku.sku_code: [
                make_fornecedor_sku(
                    katrina, preco_unitario_reais=1800, moq_unidades=48
                ),
                make_fornecedor_sku(
                    verdela, preco_unitario_reais=1950, moq_unidades=60
                ),
            ]
        },
        estoques={sku.sku_code: make_estoque(disponivel=120, reservada=10)},
        vendas=vendas,
    )


def _client(
    adapter: InMemoryERPAdapter,
    politicas: InMemoryPoliticaCompraRepositorio | None = None,
) -> TestClient:
    repo = politicas or InMemoryPoliticaCompraRepositorio()
    app.dependency_overrides[get_erp_adapter] = lambda: adapter
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: repo
    return TestClient(app)


def _cleanup() -> None:
    app.dependency_overrides.pop(get_erp_adapter, None)
    app.dependency_overrides.pop(get_politica_compra_repositorio, None)


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
        estoques={sku.sku_code: make_estoque(disponivel=50)},
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


def _adapter_com_dois_skus_um_urgente() -> InMemoryERPAdapter:
    urgente = make_sku("URG", produto_nome="Urgente")
    tranquilo = make_sku("OK", produto_nome="Tranquilo")
    vendas = [
        make_venda(urgente, datetime(2026, m, 10, tzinfo=UTC), 60, key=f"u{m}")
        for m in range(3, 9)
    ] + [
        make_venda(tranquilo, datetime(2026, m, 10, tzinfo=UTC), 60, key=f"t{m}")
        for m in range(3, 9)
    ]
    return InMemoryERPAdapter(
        skus=[urgente, tranquilo],
        estoques={
            urgente.sku_code: make_estoque(disponivel=10),
            tranquilo.sku_code: make_estoque(disponivel=1000),
        },
        vendas=vendas,
    )


def test_abaixo_do_piso_retorna_apenas_skus_em_alerta() -> None:
    client = _client(_adapter_com_dois_skus_um_urgente())
    try:
        response = client.get("/skus/abaixo-do-piso")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["sku_code"] == "URG"
    assert body[0]["produto_nome"] == "Urgente"
    assert body[0]["cobertura_meses"] > 0
    assert set(body[0].keys()) == {"sku_code", "produto_nome", "cobertura_meses"}


def test_abaixo_do_piso_dias_parametrizavel() -> None:
    client = _client(_adapter_com_dois_skus_um_urgente())
    try:
        # Piso 1 dia = 0.033 meses. Cobertura URG = 10/60 = 0.167 > 0.033.
        # Ninguém abaixo.
        response = client.get("/skus/abaixo-do-piso?dias=1")
    finally:
        _cleanup()

    assert response.status_code == 200
    assert response.json() == []


def _politica_com_piso_alerta(dias: int) -> InMemoryPoliticaCompraRepositorio:
    repo = InMemoryPoliticaCompraRepositorio()
    repo.salvar_nova_versao(
        PARAMETROS_V1.model_copy(update={"piso_alerta_dias": dias})
    )
    return repo


def test_abaixo_do_piso_sem_dias_usa_piso_alerta_da_politica() -> None:
    # URG tem cobertura de 5 dias (10 / 60 por mês). Com piso de alerta 3,
    # sai da lista; com o padrão 20, estaria nela.
    client = _client(_adapter_com_dois_skus_um_urgente(), _politica_com_piso_alerta(3))
    try:
        response = client.get("/skus/abaixo-do-piso")
    finally:
        _cleanup()

    assert response.status_code == 200
    assert response.json() == []


def test_abaixo_do_piso_com_dias_ignora_a_politica() -> None:
    client = _client(_adapter_com_dois_skus_um_urgente(), _politica_com_piso_alerta(3))
    try:
        response = client.get("/skus/abaixo-do-piso?dias=20")
    finally:
        _cleanup()

    assert response.status_code == 200
    assert [s["sku_code"] for s in response.json()] == ["URG"]


def test_abaixo_do_piso_lista_vazia() -> None:
    adapter = InMemoryERPAdapter(skus=[])
    client = _client(adapter)
    try:
        response = client.get("/skus/abaixo-do-piso")
    finally:
        _cleanup()

    assert response.status_code == 200
    assert response.json() == []


def test_vendas_retorna_serie_mensal() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/TBC-BEG-70140/vendas?meses=6")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 6
    for entry in body:
        assert "ano" in entry and "mes" in entry
        assert "quantidade_unidades" in entry
        assert "valor_total_reais" in entry
    assert body[0]["mes"] < body[-1]["mes"] or body[0]["ano"] < body[-1]["ano"]


def test_vendas_sku_inexistente_retorna_404() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/NAO-EXISTE/vendas")
    finally:
        _cleanup()

    assert response.status_code == 404


def test_vendas_sku_sem_vendas_retorna_serie_zerada() -> None:
    sku = make_sku("SEM-VENDAS")
    adapter = InMemoryERPAdapter(skus=[sku])
    client = _client(adapter)
    try:
        response = client.get("/skus/SEM-VENDAS/vendas?meses=3")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert all(e["quantidade_unidades"] == 0 for e in body)


def test_sazonalidade_retorna_doze_meses() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/TBC-BEG-70140/sazonalidade")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {str(m) for m in range(1, 13)}
    assert all(isinstance(v, float | int) for v in body.values())


def test_sazonalidade_sku_inexistente_retorna_404() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/NAO-EXISTE/sazonalidade")
    finally:
        _cleanup()

    assert response.status_code == 404


def test_sazonalidade_sku_sem_vendas_retorna_neutro() -> None:
    sku = make_sku("SEM-VENDAS")
    adapter = InMemoryERPAdapter(skus=[sku])
    client = _client(adapter)
    try:
        response = client.get("/skus/SEM-VENDAS/sazonalidade")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert all(v == 1.0 for v in body.values())
    assert len(body) == 12


def test_fornecedores_endpoint_retorna_condicoes_completas() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/TBC-BEG-70140/fornecedores")
    finally:
        _cleanup()

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    for f in body:
        assert "fornecedor_nome" in f
        assert "preco_unitario_reais" in f
        assert "moq_unidades" in f
        assert "lead_time_dias_contratado" in f
        assert "lead_time_dias_observado" in f
        assert "prazo_pagamento_padrao" in f
        assert "pedido_minimo_reais" in f


def test_fornecedores_sku_inexistente_retorna_404() -> None:
    client = _client(_adapter_completo())
    try:
        response = client.get("/skus/NAO-EXISTE/fornecedores")
    finally:
        _cleanup()

    assert response.status_code == 404


def test_fornecedores_sku_sem_fornecedores_retorna_lista_vazia() -> None:
    sku = make_sku("SOZINHO")
    adapter = InMemoryERPAdapter(skus=[sku])
    client = _client(adapter)
    try:
        response = client.get("/skus/SOZINHO/fornecedores")
    finally:
        _cleanup()

    assert response.status_code == 200
    assert response.json() == []
