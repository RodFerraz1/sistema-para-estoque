"""Testes HTTP da gestão de usuários pelo admin (`/usuarios`) e da troca da própria senha
(`/eu/senha`), com login de verdade. Cenário em `cenario_usuarios.py`."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_usuarios import (  # noqa: F401 (fixtures)
    SENHA,
    XRW,
    Cenario,
    cenario,
    client,
    entrar,
)
from src.main import app
from src.usuarios.schemas import Papel

pytestmark = pytest.mark.login_de_verdade


@pytest.fixture
def admin(client: TestClient, cenario: Cenario) -> TestClient:
    entrar(client, cenario.pessoa("Rodrigo", "admin"))
    return client


def test_admin_cadastra_uma_pessoa_que_entra_com_a_senha_inicial(admin: TestClient, cenario: Cenario) -> None:
    response = admin.post(
        "/usuarios",
        json={"nome": "Bia", "email": "Bia@Loja.com", "senha": "senha-inicial", "papeis": ["reposicao", "vendas"]},
        headers=XRW,
    )

    assert response.status_code == 201
    criada = response.json()
    assert {k: criada[k] for k in ("nome", "email", "papeis", "ativo", "ultimo_acesso_em")} == {
        "nome": "Bia",
        "email": "bia@loja.com",
        "papeis": ["vendas", "reposicao"],
        "ativo": True,
        "ultimo_acesso_em": None,
    }
    assert "senha_hash" not in criada
    assert entrar(TestClient(app), "bia@loja.com", "senha-inicial")["papeis"] == ["vendas", "reposicao"]


def test_lista_traz_papeis_situacao_e_ultimo_acesso_pelo_nome(admin: TestClient, cenario: Cenario) -> None:
    cenario.pessoa("Carla", "comprador")
    cenario.relogio.avancar(hours=2)
    entrar(TestClient(app), cenario.pessoa("Bia", "vendas"))

    lista = admin.get("/usuarios").json()

    assert [(u["nome"], u["papeis"], u["ativo"], u["ultimo_acesso_em"]) for u in lista] == [
        ("Bia", ["vendas"], True, "2026-10-01T11:00:00Z"),
        ("Carla", ["comprador"], True, None),
        ("Rodrigo", ["admin"], True, "2026-10-01T11:00:00Z"),
    ]


def test_email_repetido_responde_409(admin: TestClient, cenario: Cenario) -> None:
    cenario.pessoa("Bia", "vendas")
    corpo = {"nome": "Outra Bia", "email": "BIA@loja.com", "senha": SENHA, "papeis": ["vendas"]}

    response = admin.post("/usuarios", json=corpo, headers=XRW)

    assert response.status_code == 409
    assert "bia@loja.com" in response.json()["detail"]


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": " ", "email": "bia@loja.com", "senha": SENHA, "papeis": ["vendas"]},
        {"nome": "Bia", "email": "bia", "senha": SENHA, "papeis": ["vendas"]},
        {"nome": "Bia", "email": "bia@loja.com", "senha": "curta", "papeis": ["vendas"]},
        {"nome": "Bia", "email": "bia@loja.com", "senha": SENHA, "papeis": []},
        {"nome": "Bia", "email": "bia@loja.com", "senha": SENHA, "papeis": ["gerente"]},
    ],
    ids=["sem-nome", "email-invalido", "senha-curta", "sem-papel", "papel-desconhecido"],
)
def test_cadastro_invalido_responde_422(admin: TestClient, corpo: dict) -> None:
    response = admin.post("/usuarios", json=corpo, headers=XRW)

    assert response.status_code == 422
    assert [u["nome"] for u in admin.get("/usuarios").json()] == ["Rodrigo"]


def _id(admin: TestClient, nome: str) -> str:
    return next(u["id"] for u in admin.get("/usuarios").json() if u["nome"] == nome)


def test_desativar_revoga_as_sessoes_e_a_pessoa_nao_entra_mais(admin: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")
    celular, computador = TestClient(app), TestClient(app)
    entrar(celular, email)
    entrar(computador, email)

    response = admin.post(f"/usuarios/{_id(admin, 'Bia')}/desativar", headers=XRW)

    assert response.status_code == 200
    assert response.json()["ativo"] is False
    assert celular.get("/eu").status_code == 401
    assert computador.get("/eu").status_code == 401
    login = TestClient(app).post("/login", json={"email": email, "senha": SENHA}, headers=XRW)
    assert login.status_code == 401
    assert [(u["nome"], u["ativo"]) for u in admin.get("/usuarios").json()] == [("Bia", False), ("Rodrigo", True)]


def test_reativar_deixa_entrar_de_novo_mas_nao_revive_a_sessao_antiga(admin: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")
    celular = TestClient(app)
    entrar(celular, email)
    bia = _id(admin, "Bia")
    admin.post(f"/usuarios/{bia}/desativar", headers=XRW)

    response = admin.post(f"/usuarios/{bia}/reativar", headers=XRW)

    assert response.json()["ativo"] is True
    assert celular.get("/eu").status_code == 401
    entrar(celular, email)
    assert celular.get("/eu").status_code == 200


def test_admin_nao_desativa_a_propria_conta(admin: TestClient) -> None:
    response = admin.post(f"/usuarios/{_id(admin, 'Rodrigo')}/desativar", headers=XRW)

    assert response.status_code == 422
    assert admin.get("/eu").status_code == 200


def test_editar_papeis_muda_o_que_a_pessoa_ve(admin: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")
    bia = TestClient(app)
    entrar(bia, email)

    response = admin.put(f"/usuarios/{_id(admin, 'Bia')}/papeis", json={"papeis": ["reposicao", "vendas"]}, headers=XRW)

    assert response.status_code == 200
    assert response.json()["papeis"] == ["vendas", "reposicao"]
    assert bia.get("/eu").json()["papeis"] == ["vendas", "reposicao"]


@pytest.mark.parametrize("papeis", [[], ["comprador"]], ids=["sem-papel", "tirando-o-proprio-admin"])
def test_papeis_invalidos_respondem_422(admin: TestClient, papeis: list[str]) -> None:
    response = admin.put(f"/usuarios/{_id(admin, 'Rodrigo')}/papeis", json={"papeis": papeis}, headers=XRW)

    assert response.status_code == 422
    assert admin.get("/eu").json()["papeis"] == ["admin"]


def test_pessoa_desconhecida_responde_404(admin: TestClient) -> None:
    ninguem = "00000000-0000-0000-0000-000000000000"

    assert admin.post(f"/usuarios/{ninguem}/desativar", headers=XRW).status_code == 404
    assert admin.put(f"/usuarios/{ninguem}/senha", json={"senha": SENHA}, headers=XRW).status_code == 404


def test_admin_redefine_a_senha_de_quem_esqueceu(admin: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")

    response = admin.put(f"/usuarios/{_id(admin, 'Bia')}/senha", json={"senha": "senha-nova-da-bia"}, headers=XRW)

    assert response.status_code == 200
    entrar(TestClient(app), email, "senha-nova-da-bia")
    antiga = TestClient(app).post("/login", json={"email": email, "senha": SENHA}, headers=XRW)
    assert antiga.status_code == 401


def test_redefinir_com_senha_curta_responde_422(admin: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")

    response = admin.put(f"/usuarios/{_id(admin, 'Bia')}/senha", json={"senha": "curta"}, headers=XRW)

    assert response.status_code == 422
    entrar(TestClient(app), email)


@pytest.mark.parametrize("papel", ["comprador", "vendas", "reposicao"])
def test_quem_nao_e_admin_recebe_403(client: TestClient, cenario: Cenario, papel: Papel) -> None:
    entrar(client, cenario.pessoa("Joana", papel))

    assert client.get("/usuarios").status_code == 403
    response = client.post(
        "/usuarios", json={"nome": "Bia", "email": "bia@loja.com", "senha": SENHA, "papeis": ["admin"]}, headers=XRW
    )
    assert response.status_code == 403
    assert cenario.repo.por_email("bia@loja.com") is None


def test_pessoa_troca_a_propria_senha_e_continua_logada(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Bia", "vendas")
    entrar(client, email)

    response = client.put("/eu/senha", json={"senha_atual": SENHA, "nova_senha": "outra-senha-boa"}, headers=XRW)

    assert response.status_code == 204
    assert client.get("/eu").status_code == 200
    entrar(TestClient(app), email, "outra-senha-boa")


@pytest.mark.parametrize(
    ("senha_atual", "nova_senha", "mensagem"),
    [("errada-demais", "outra-senha-boa", "A senha atual não confere."), (SENHA, "curta", "pelo menos 8")],
    ids=["senha-atual-errada", "nova-curta"],
)
def test_troca_de_senha_invalida_responde_422_sem_derrubar_a_sessao(
    client: TestClient, cenario: Cenario, senha_atual: str, nova_senha: str, mensagem: str
) -> None:
    email = cenario.pessoa("Bia", "vendas")
    entrar(client, email)

    response = client.put("/eu/senha", json={"senha_atual": senha_atual, "nova_senha": nova_senha}, headers=XRW)

    assert response.status_code == 422
    assert mensagem in response.json()["detail"]
    assert client.get("/eu").status_code == 200
    entrar(TestClient(app), email)
