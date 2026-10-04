"""Smoke do login de verdade contra o Postgres: senha com argon2id, sessão no cookie,
papel que decide o que a pessoa vê e saída que revoga a sessão. A pessoa do smoke é
criada e apagada pelo próprio teste."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.seed import RUPTURA_COM_PEDIDO_ATRASADO
from src.db.engine import get_engine
from src.main import app
from src.usuarios.postgres import (
    PostgresSessoesRepositorio,
    PostgresTentativasLoginRepositorio,
    PostgresUsuariosRepositorio,
)
from src.usuarios.schemas import Usuario
from src.usuarios.service import Usuarios

pytestmark = [pytest.mark.smoke, pytest.mark.login_de_verdade]

SENHA = "smoke-girassol-azul"
XRW = {"X-Requested-With": "fetch"}


@pytest.fixture
def vendedora() -> Iterator[Usuario]:
    engine = get_engine()
    usuarios = Usuarios(
        PostgresUsuariosRepositorio(engine), PostgresSessoesRepositorio(engine), PostgresTentativasLoginRepositorio(engine)
    )
    usuario = usuarios.criar("Vendedora do smoke", "vendedora-smoke@copilot.teste", SENHA, ["vendas"])
    yield usuario
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM copilot.sessoes WHERE usuario_id = :id"), {"id": usuario.id})
        conn.execute(text("DELETE FROM copilot.tentativas_login WHERE email = :email"), {"email": usuario.email})
        conn.execute(text("DELETE FROM copilot.usuarios WHERE id = :id"), {"id": usuario.id})


def test_login_papel_e_saida_contra_o_banco(vendedora: Usuario) -> None:
    client = TestClient(app)
    credenciais = {"email": vendedora.email, "senha": SENHA}
    assert client.get("/eu").status_code == 401
    assert client.post("/login", json=credenciais).status_code == 403
    assert client.post("/login", json={**credenciais, "senha": "errada"}, headers=XRW).status_code == 401

    response = client.post("/login", json=credenciais, headers=XRW)
    assert response.status_code == 200
    assert response.json()["papeis"] == ["vendas"]
    assert client.get("/eu").json()["email"] == vendedora.email

    assert client.get("/painel").status_code == 403
    disponibilidade = client.get(f"/skus/{RUPTURA_COM_PEDIDO_ATRASADO}/disponibilidade")
    assert disponibilidade.status_code == 200
    [entrega] = disponibilidade.json()["entregas"]
    assert entrega["atrasada"] and set(entrega) == {"quantidade", "previsao", "atrasada"}

    assert client.post("/logout", headers=XRW).status_code == 204
    assert client.get("/eu").status_code == 401
