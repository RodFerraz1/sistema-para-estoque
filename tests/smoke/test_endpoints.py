"""Smoke test end-to-end: valida o contrato de cada endpoint público.

Executa contra o Postgres real com o seed populado. Não faz asserções
sobre valores exatos (que variam com a data de execução do seed) - só
sobre status code, shape (via os DTOs Pydantic da camada API) e
invariantes que valem pra qualquer seed (versão nova da política vira a
ativa, pedido em trânsito entra na posição). Serve de regression net
pros próximos specs.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.api.schemas import (
    AnaliseSKUResponse,
    FornecedorResponse,
    PoliticaCompraResponse,
    SKUAbaixoDoPisoResponse,
    SugestaoPedidoResponse,
    VendaMensalResponse,
)
from src.db.engine import get_engine
from src.inventory.schemas import STATUS_EM_TRANSITO

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


def test_abaixo_do_piso_sem_dias_usa_politica(client: TestClient) -> None:
    response = client.get("/skus/abaixo-do-piso")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for entry in body:
        item = SKUAbaixoDoPisoResponse.model_validate(entry)
        assert item.cobertura_meses >= 0

    politica = PoliticaCompraResponse.model_validate(
        client.get("/politica-compra").json()
    )
    com_piso_da_politica = client.get(
        "/skus/abaixo-do-piso",
        params={"dias": politica.parametros.piso_alerta_dias},
    )
    assert body == com_piso_da_politica.json()


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


def test_politica_compra_ativa(client: TestClient) -> None:
    response = client.get("/politica-compra")
    assert response.status_code == 200
    politica = PoliticaCompraResponse.model_validate(response.json())
    assert politica.versao >= 1


@pytest.fixture
def _descarta_versoes_novas_da_politica() -> Iterator[None]:
    with get_engine().connect() as conn:
        antes = conn.execute(
            text("SELECT MAX(versao) FROM copilot.politicas_compra")
        ).scalar_one()
    yield
    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM copilot.politicas_compra WHERE versao > :v"), {"v": antes}
        )


@pytest.mark.usefixtures("_descarta_versoes_novas_da_politica")
def test_put_politica_compra_cria_versao_nova(client: TestClient) -> None:
    ativa = PoliticaCompraResponse.model_validate(client.get("/politica-compra").json())

    response = client.put(
        "/politica-compra", json=ativa.parametros.model_dump(mode="json")
    )
    assert response.status_code == 201
    nova = PoliticaCompraResponse.model_validate(response.json())
    assert nova.versao > ativa.versao
    assert nova.parametros == ativa.parametros

    seguinte = PoliticaCompraResponse.model_validate(
        client.get("/politica-compra").json()
    )
    assert seguinte.versao == nova.versao


def test_sugestao_compra_shape(client: TestClient, sku_code: str) -> None:
    response = client.get(f"/skus/{sku_code}/sugestao-compra")
    assert response.status_code == 200
    sugestao = SugestaoPedidoResponse.model_validate(response.json())
    assert sugestao.sku_code == sku_code
    assert sugestao.quantidade >= 0
    assert (sugestao.motivo is None) == (sugestao.quantidade > 0)
    assert sugestao.politica_versao >= 1


def test_sugestao_compra_sku_inexistente_404(client: TestClient) -> None:
    response = client.get("/skus/NAO-EXISTE-999/sugestao-compra")
    assert response.status_code == 404


def test_sugestao_compra_conta_estoque_em_transito(client: TestClient) -> None:
    with get_engine().connect() as conn:
        skus_com_pedido_aberto = conn.execute(
            text(
                """
                SELECT DISTINCT s.sku_code
                FROM erp.pedidos_compra_itens i
                JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                JOIN erp.skus s ON s.id = i.sku_id
                WHERE p.status::text = ANY(:status)
                  AND i.quantidade > i.quantidade_recebida
                ORDER BY s.sku_code
                """
            ),
            {"status": list(STATUS_EM_TRANSITO)},
        ).scalars().all()
    assert skus_com_pedido_aberto

    def em_transito_no_calculo(sku_code: str) -> int:
        response = client.get(f"/skus/{sku_code}/sugestao-compra")
        assert response.status_code == 200
        calculo = SugestaoPedidoResponse.model_validate(response.json()).calculo
        return calculo.em_transito if calculo is not None else 0

    assert any(em_transito_no_calculo(c) > 0 for c in skus_com_pedido_aberto)
