"""O usuário fake que o `conftest.py` da raiz põe em todo teste HTTP."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.usuarios.schemas import Usuario


def test_sem_marcador_o_fake_tem_todos_os_papeis(usuario_logado: Usuario) -> None:
    eu = TestClient(app).get("/eu").json()

    assert eu["nome"] == usuario_logado.nome
    assert eu["papeis"] == ["comprador", "vendas", "reposicao", "admin"]


@pytest.mark.papeis("vendas")
def test_o_marcador_papeis_restringe_o_fake() -> None:
    client = TestClient(app)

    assert client.get("/eu").json()["papeis"] == ["vendas"]
    assert client.get("/politica-compra").status_code == 403
