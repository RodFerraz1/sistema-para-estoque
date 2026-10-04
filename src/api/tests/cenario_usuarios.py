"""Cenário dos testes HTTP com login de verdade: repositórios de usuários, sessões e
tentativas em memória e relógio controlado. Quem usa marca o módulo com
`pytest.mark.login_de_verdade`."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.usuarios.dependencies import (
    get_relogio,
    get_sessoes_repositorio,
    get_tentativas_login_repositorio,
    get_usuarios_repositorio,
)
from src.usuarios.in_memory import (
    InMemorySessoesRepositorio,
    InMemoryTentativasLoginRepositorio,
    InMemoryUsuariosRepositorio,
)
from src.usuarios.schemas import Papel
from src.usuarios.service import Usuarios
from tests.fakes import RelogioFake

AGORA = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
SENHA = "girassol-azul"
XRW = {"X-Requested-With": "fetch"}
DEPENDENCIAS = (get_usuarios_repositorio, get_sessoes_repositorio, get_tentativas_login_repositorio, get_relogio)


@dataclass
class Cenario:
    usuarios: Usuarios
    repo: InMemoryUsuariosRepositorio
    sessoes: InMemorySessoesRepositorio
    relogio: RelogioFake

    def pessoa(self, nome: str, *papeis: Papel) -> str:
        email = f"{nome.lower()}@loja.com"
        self.usuarios.criar(nome, email, SENHA, list(papeis))
        return email


@pytest.fixture
def cenario() -> Iterator[Cenario]:
    usuarios, sessoes, tentativas = (
        InMemoryUsuariosRepositorio(),
        InMemorySessoesRepositorio(),
        InMemoryTentativasLoginRepositorio(),
    )
    relogio = RelogioFake(AGORA)
    app.dependency_overrides[get_usuarios_repositorio] = lambda: usuarios
    app.dependency_overrides[get_sessoes_repositorio] = lambda: sessoes
    app.dependency_overrides[get_tentativas_login_repositorio] = lambda: tentativas
    app.dependency_overrides[get_relogio] = lambda: relogio
    yield Cenario(Usuarios(usuarios, sessoes, tentativas, relogio=relogio), usuarios, sessoes, relogio)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def entrar(client: TestClient, email: str, senha: str = SENHA) -> dict:
    response = client.post("/login", json={"email": email, "senha": senha}, headers=XRW)
    assert response.status_code == 200, response.text
    return response.json()
