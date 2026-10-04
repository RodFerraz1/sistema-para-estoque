"""Testes HTTP dos setores da loja (`/setores`) e do setor conhecido de um SKU
(`/skus/{sku}/setor`). O admin mantém a lista; a vendedora e o repositor leem só os setores
ativos. Cenário em `cenario_painel.py`."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    INATIVO,
    ZERADO,
    client,  # noqa: F401 (fixture)
    preparar,
)
from src.main import app
from src.reposicao.schemas import Setor, SetorDoSku
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Papel
from tests.fakes import make_usuario


def criar(client: TestClient, nome: str) -> dict:
    response = client.post("/setores", json={"nome": nome})
    assert response.status_code == 201, response.text
    return response.json()


def setores(client: TestClient) -> list[dict]:
    response = client.get("/setores")
    assert response.status_code == 200, response.text
    return response.json()


def test_o_admin_cria_setores_e_ve_a_lista_pelo_nome(client: TestClient) -> None:
    preparar()

    criado = criar(client, "  Tapetes  ")
    criar(client, "Banho")

    assert criado["nome"] == "Tapetes"
    assert criado["ativo"] is True
    assert [(s["nome"], s["ativo"], s["skus_conhecidos"]) for s in setores(client)] == [
        ("Banho", True, 0),
        ("Tapetes", True, 0),
    ]


def test_o_admin_renomeia_e_desativa_um_setor(client: TestClient) -> None:
    preparar()
    tapetes = criar(client, "Tapetes")

    response = client.put(f"/setores/{tapetes['id']}", json={"nome": "Tapetes e capachos", "ativo": False})

    assert response.status_code == 200, response.text
    assert [(s["nome"], s["ativo"]) for s in setores(client)] == [("Tapetes e capachos", False)]


def test_nome_repetido_responde_409_e_vazio_422(client: TestClient) -> None:
    preparar()
    criar(client, "Tapetes")
    banho = criar(client, "Banho")

    assert client.post("/setores", json={"nome": "tapetes"}).status_code == 409
    assert client.put(f"/setores/{banho['id']}", json={"nome": "TAPETES", "ativo": True}).status_code == 409
    assert client.post("/setores", json={"nome": "   "}).status_code == 422


def test_mudar_setor_que_nao_existe_responde_404(client: TestClient) -> None:
    preparar()

    assert client.put(f"/setores/{uuid4()}", json={"nome": "Cama", "ativo": True}).status_code == 404


def test_a_lista_conta_os_skus_de_setor_conhecido(client: TestClient) -> None:
    cenario = preparar()
    tapetes = criar(client, "Tapetes")
    for sku in ("TAP-MARR-4060-01", "TAP-CINZ-4060-02"):
        cenario.setores.lembrar(
            SetorDoSku(sku_code=sku, setor_id=tapetes["id"], atualizado_em=cenario.relogio.agora, usuario_id=None)
        )

    [setor] = setores(client)

    assert setor["skus_conhecidos"] == 2


@pytest.mark.parametrize("papel", ["vendas", "reposicao"])
def test_vendedora_e_repositor_veem_so_os_setores_ativos(client: TestClient, papel: Papel) -> None:
    cenario = preparar()
    cenario.setores.gravar(Setor(id=uuid4(), nome="Tapetes", ativo=True))
    cenario.setores.gravar(Setor(id=uuid4(), nome="Cozinha", ativo=False))
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert [s["nome"] for s in setores(client)] == ["Tapetes"]


@pytest.mark.parametrize("papel", ["comprador", "vendas", "reposicao"])
def test_so_o_admin_cria_e_muda_setores(client: TestClient, papel: Papel) -> None:
    cenario = preparar()
    setor = Setor(id=uuid4(), nome="Tapetes", ativo=True)
    cenario.setores.gravar(setor)
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert client.post("/setores", json={"nome": "Banho"}).status_code == 403
    assert client.put(f"/setores/{setor.id}", json={"nome": "Banho", "ativo": True}).status_code == 403


def test_o_comprador_nao_le_os_setores(client: TestClient) -> None:
    preparar()
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=["comprador"])

    assert client.get("/setores").status_code == 403


def test_setor_do_sku_vem_vazio_ate_alguem_dizer_onde_ele_fica(client: TestClient) -> None:
    cenario = preparar()
    tapetes = Setor(id=uuid4(), nome="Tapetes", ativo=True)
    cenario.setores.gravar(tapetes)

    antes = client.get(f"/skus/{ZERADO.sku_code}/setor")
    cenario.setores.lembrar(
        SetorDoSku(sku_code=ZERADO.sku_code, setor_id=tapetes.id, atualizado_em=cenario.relogio.agora, usuario_id=None)
    )
    depois = client.get(f"/skus/{ZERADO.sku_code}/setor")

    assert antes.status_code == 200
    assert antes.json() == {"sku_code": ZERADO.sku_code, "setor": None}
    assert depois.json()["setor"] == {"id": str(tapetes.id), "nome": "Tapetes", "ativo": True}


def test_setor_de_sku_que_nao_existe_responde_404(client: TestClient) -> None:
    preparar()

    assert client.get("/skus/NAO-EXISTE/setor").status_code == 404
    assert client.get(f"/skus/{INATIVO.sku_code}/setor").status_code == 200


@pytest.mark.parametrize(("papel", "status"), [("vendas", 200), ("reposicao", 200), ("comprador", 403), ("admin", 403)])
def test_quem_le_o_setor_do_sku(client: TestClient, papel: Papel, status: int) -> None:
    preparar()
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert client.get(f"/skus/{ZERADO.sku_code}/setor").status_code == status

