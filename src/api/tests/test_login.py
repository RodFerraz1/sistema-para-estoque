"""Testes HTTP do login de verdade (`/login`, `/logout`, `/eu`), da sessão, do bloqueio e
das respostas 401 e 403, sem o usuário fake dos outros testes HTTP."""
from __future__ import annotations

import hashlib
import re
from uuid import uuid4

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
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.usuarios.dependencies import NOME_DO_COOKIE
from src.usuarios.schemas import PAPEIS, Papel
from tests.fakes import make_sku

pytestmark = pytest.mark.login_de_verdade


def test_login_abre_sessao_em_cookie_e_eu_devolve_os_papeis(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas", "reposicao")

    response = client.post("/login", json={"email": "  Joana@Loja.com ", "senha": SENHA}, headers=XRW)

    assert response.status_code == 200
    corpo = response.json()
    assert {k: corpo[k] for k in ("nome", "email", "papeis")} == {
        "nome": "Joana",
        "email": email,
        "papeis": ["vendas", "reposicao"],
    }
    assert "senha_hash" not in corpo
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{NOME_DO_COOKIE}=")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Max-Age=2592000" in cookie
    assert "Secure" not in cookie
    assert client.get("/eu").json() == corpo


def test_banco_guarda_so_o_hash_do_token(client: TestClient, cenario: Cenario) -> None:
    entrar(client, cenario.pessoa("Joana", "vendas"))
    token = client.cookies[NOME_DO_COOKIE]

    assert cenario.sessoes.por_token_hash(token) is None
    assert cenario.sessoes.por_token_hash(hashlib.sha256(token.encode()).hexdigest()) is not None


def test_senha_errada_e_email_desconhecido_respondem_401_sem_cookie(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas")

    for credenciais in ({"email": email, "senha": "errada"}, {"email": "ninguem@loja.com", "senha": SENHA}):
        response = client.post("/login", json=credenciais, headers=XRW)
        assert response.status_code == 401
        assert response.json()["detail"] == "E-mail ou senha incorretos."
        assert "set-cookie" not in response.headers


def test_sem_sessao_responde_401(client: TestClient, cenario: Cenario) -> None:
    assert client.get("/eu").status_code == 401
    client.cookies.set(NOME_DO_COOKIE, "token-inventado")
    assert client.get("/eu").status_code == 401


def test_sessao_vale_30_dias_desde_o_ultimo_uso(client: TestClient, cenario: Cenario) -> None:
    entrar(client, cenario.pessoa("Joana", "vendas"))

    cenario.relogio.avancar(days=29)
    assert client.get("/eu").status_code == 200
    cenario.relogio.avancar(days=29)
    response = client.get("/eu")
    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]

    cenario.relogio.avancar(days=30)
    assert client.get("/eu").status_code == 401


def test_sair_revoga_a_sessao(client: TestClient, cenario: Cenario) -> None:
    entrar(client, cenario.pessoa("Joana", "vendas"))
    token = client.cookies[NOME_DO_COOKIE]

    response = client.post("/logout", headers=XRW)

    assert response.status_code == 204
    assert 'Max-Age=0' in response.headers["set-cookie"]
    client.cookies.set(NOME_DO_COOKIE, token)
    assert client.get("/eu").status_code == 401


def test_usuario_desativado_nao_entra(client: TestClient, cenario: Cenario) -> None:
    ativo = cenario.usuarios.criar("Joana", "joana@loja.com", SENHA, ["vendas"])
    cenario.repo.gravar(ativo.model_copy(update={"id": uuid4(), "email": "bia@loja.com", "ativo": False}))

    response = client.post("/login", json={"email": "bia@loja.com", "senha": SENHA}, headers=XRW)

    assert response.status_code == 401


def test_cinco_erros_em_15_minutos_bloqueiam_o_email_por_15_minutos(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas")
    outro = cenario.pessoa("Bia", "vendas")
    for _ in range(5):
        client.post("/login", json={"email": email, "senha": "errada"}, headers=XRW)
        cenario.relogio.avancar(minutes=3)

    bloqueado = client.post("/login", json={"email": email, "senha": SENHA}, headers=XRW)

    assert bloqueado.status_code == 429
    assert "15 minutos" in bloqueado.json()["detail"]
    assert "set-cookie" not in bloqueado.headers
    entrar(client, outro)

    cenario.relogio.avancar(minutes=12)
    entrar(client, email)


def test_erros_espalhados_alem_de_15_minutos_nao_bloqueiam(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas")
    for _ in range(5):
        client.post("/login", json={"email": email, "senha": "errada"}, headers=XRW)
        cenario.relogio.avancar(minutes=4)

    entrar(client, email)


def test_acerto_zera_as_tentativas_erradas(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas")
    for _ in range(4):
        client.post("/login", json={"email": email, "senha": "errada"}, headers=XRW)
    entrar(client, email)

    client.post("/login", json={"email": email, "senha": "errada"}, headers=XRW)

    entrar(client, email)


def test_mudanca_de_estado_sem_x_requested_with_responde_403(client: TestClient, cenario: Cenario) -> None:
    email = cenario.pessoa("Joana", "vendas")

    response = client.post("/login", json={"email": email, "senha": SENHA})

    assert response.status_code == 403
    assert "set-cookie" not in response.headers


def test_papel_errado_responde_403(client: TestClient, cenario: Cenario) -> None:
    entrar(client, cenario.pessoa("Joana", "vendas"))

    response = client.get("/politica-compra")

    assert response.status_code == 403
    assert response.json()["detail"] == "Esta parte do Copilot não é do seu papel."


ROTAS_LIVRES = {("GET", "/health"), ("POST", "/login")}


def _caminho(rota: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", rota)


def _rotas() -> list[tuple[str, str]]:
    return [
        (metodo.upper(), caminho)
        for caminho, operacoes in app.openapi()["paths"].items()
        for metodo in operacoes
    ]


def test_toda_rota_exige_login_menos_o_health_e_o_login(client: TestClient, cenario: Cenario) -> None:
    rotas = _rotas()
    assert len(rotas) > 15

    sem_401 = [
        (metodo, caminho)
        for metodo, caminho in rotas
        if (metodo, caminho) not in ROTAS_LIVRES
        and client.request(metodo, _caminho(caminho), headers=XRW).status_code != 401
    ]

    assert sem_401 == []


PAPEIS_POR_ROTA: dict[tuple[str, str], set[Papel]] = {
    ("GET", "/skus"): {"comprador", "vendas", "reposicao"},
    ("POST", "/avisos"): {"vendas"},
    ("GET", "/reposicao/painel"): {"reposicao"},
    ("GET", "/categorias"): {"comprador", "reposicao"},
    ("GET", "/usuarios"): {"admin"},
    ("POST", "/usuarios"): {"admin"},
    ("PUT", "/usuarios/{usuario_id}/papeis"): {"admin"},
    ("POST", "/usuarios/{usuario_id}/desativar"): {"admin"},
    ("POST", "/usuarios/{usuario_id}/reativar"): {"admin"},
    ("PUT", "/usuarios/{usuario_id}/senha"): {"admin"},
}
DE_QUALQUER_UM = {
    ("GET", "/eu"),
    ("POST", "/logout"),
    ("PUT", "/eu/senha"),
    ("GET", "/notificacoes"),
    ("POST", "/notificacoes/vistas"),
}


def test_cada_rota_recusa_quem_nao_tem_o_papel_do_mapa(cenario: Cenario) -> None:
    """Fora do `PAPEIS_POR_ROTA` e das rotas de qualquer pessoa logada, tudo é do comprador.
    Só confere os papéis recusados, para nenhuma rota rodar de verdade."""
    clientes = {}
    for papel in PAPEIS:
        clientes[papel] = TestClient(app)
        entrar(clientes[papel], cenario.pessoa(f"So{papel}", papel))

    errados = [
        (metodo, caminho, papel, status)
        for metodo, caminho in _rotas()
        if (metodo, caminho) not in ROTAS_LIVRES | DE_QUALQUER_UM
        for papel in PAPEIS
        if papel not in PAPEIS_POR_ROTA.get((metodo, caminho), {"comprador"})
        and (status := clientes[papel].request(metodo, _caminho(caminho), headers=XRW).status_code) != 403
    ]

    assert errados == []


@pytest.mark.parametrize("papel", ["comprador", "vendas", "reposicao"])
def test_quem_vende_repoe_ou_compra_busca_skus(client: TestClient, cenario: Cenario, papel: Papel) -> None:
    app.dependency_overrides[get_erp_adapter] = lambda: InMemoryERPAdapter(skus=[make_sku("TBC-BRAN-70140-01")])
    try:
        entrar(client, cenario.pessoa("Joana", papel))

        response = client.get("/skus", params={"busca": "TBC-BRAN"})
    finally:
        app.dependency_overrides.pop(get_erp_adapter, None)

    assert response.status_code == 200
    assert [s["sku_code"] for s in response.json()] == ["TBC-BRAN-70140-01"]
