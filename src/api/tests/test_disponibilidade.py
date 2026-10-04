"""Testes HTTP da consulta da vendedora (`/skus/{sku}/disponibilidade`): se tem estoque, se
vem compra e quando chega, com a nova previsão da cobrança quando houver. Cenário em
`cenario_painel.py`: hoje é 01/10/2026, piso de alerta de 20 dias, `ZERADO` sem nada,
`URGENTE` segura 15 dias e `REGULAR` 45. `PISO` tem 100 a caminho da Boa Vista, sem data
prevista."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    BOA_VISTA,
    KATRINA,
    PISO,
    REGULAR,
    URGENTE,
    ZERADO,
    atrasar,
    client,  # noqa: F401 (fixture)
    preparar,
)
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import PedidoCompra


def disponibilidade(client: TestClient, sku: SKU) -> dict:
    response = client.get(f"/skus/{sku.sku_code}/disponibilidade")
    assert response.status_code == 200, response.text
    return response.json()


def cobrar(client: TestClient, pedido: PedidoCompra, **corpo: str) -> None:
    response = client.post(f"/pedidos/{pedido.id}/cobrancas", json=corpo)
    assert response.status_code == 201, response.text


def test_sku_zerado_acabou_e_sem_compra_nao_vem_nada(client: TestClient) -> None:
    preparar()

    assert disponibilidade(client, ZERADO) == {
        "sku_code": ZERADO.sku_code,
        "produto_nome": "Toalha Banho Conforto",
        "cor": "lilás",
        "tamanho": "70x140",
        "disponivel": 0,
        "situacao": "acabou",
        "entregas": [],
    }


@pytest.mark.parametrize(("sku", "situacao", "disponivel"), [(URGENTE, "pouco", 50), (REGULAR, "tem", 150)])
def test_tem_pouco_quando_esta_em_ruptura(client: TestClient, sku: SKU, situacao: str, disponivel: int) -> None:
    preparar()

    resultado = disponibilidade(client, sku)

    assert resultado["situacao"] == situacao
    assert resultado["disponivel"] == disponivel


def test_compra_sem_data_prevista_vem_sem_previsao_e_nao_esta_atrasada(client: TestClient) -> None:
    preparar()

    assert disponibilidade(client, PISO)["entregas"] == [{"quantidade": 100, "previsao": None, "atrasada": False}]


def test_previsao_vencida_esta_atrasada_e_a_no_prazo_nao(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (ZERADO, 30), prevista=date(2026, 9, 30), key="vencido")
    atrasar(cenario, KATRINA, (ZERADO, 40), prevista=date(2026, 10, 15), key="no-prazo", recebida=10)

    assert disponibilidade(client, ZERADO)["entregas"] == [
        {"quantidade": 30, "previsao": "2026-09-30", "atrasada": True},
        {"quantidade": 30, "previsao": "2026-10-15", "atrasada": False},
    ]


def test_a_nova_previsao_da_cobranca_vale_no_lugar_da_do_pedido(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (ZERADO, 30), prevista=date(2026, 9, 20))

    cobrar(client, pedido, nova_previsao="2026-10-15")

    assert disponibilidade(client, ZERADO)["entregas"] == [
        {"quantidade": 30, "previsao": "2026-10-15", "atrasada": False}
    ]


def test_cobranca_sem_nova_previsao_deixa_a_entrega_atrasada(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (ZERADO, 30), prevista=date(2026, 9, 20))

    cobrar(client, pedido, comentario="Cobrei por telefone.")

    assert disponibilidade(client, ZERADO)["entregas"] == [
        {"quantidade": 30, "previsao": "2026-09-20", "atrasada": True}
    ]


def test_nova_previsao_que_passou_volta_a_ficar_atrasada(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (ZERADO, 30), prevista=date(2026, 9, 20))
    cobrar(client, pedido, nova_previsao="2026-10-03")

    cenario.relogio.avancar(days=3)

    assert disponibilidade(client, ZERADO)["entregas"] == [
        {"quantidade": 30, "previsao": "2026-10-03", "atrasada": True}
    ]


def test_sku_que_nao_existe_responde_404(client: TestClient) -> None:
    preparar()

    assert client.get("/skus/NAO-EXISTE/disponibilidade").status_code == 404
