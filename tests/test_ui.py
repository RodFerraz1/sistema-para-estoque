"""Testes HTTP da UI estática em `/ui` e dos endpoints que os `.js` chamam."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.main import UI_DIR, app
from src.politica_compra.schemas import MotivoDestaque

PAGINAS = ["index.html", "chat.html", "politica.html"]
TIPOS = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
REFERENCIA_NO_HTML = re.compile(r'(?:src|href)="([^"]+)"')
IMPORT_NO_JS = re.compile(r'from\s+"\./([^"]+)"')
CHAMADA_DA_API = re.compile(r'api\(\s*"([A-Z]+)",\s*["`]([^"`]+)["`]')
PARAMETRO_NO_TEMPLATE = re.compile(r"\$\{[^}]+\}")
PARAMETRO_NA_ROTA = re.compile(r"\{[^}]+\}")
ID_DE_EXEMPLO = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _assets() -> set[str]:
    assets: set[str] = set()
    for pagina in PAGINAS:
        assets |= set(REFERENCIA_NO_HTML.findall((UI_DIR / pagina).read_text()))
    for script in UI_DIR.glob("*.js"):
        assets |= set(IMPORT_NO_JS.findall(script.read_text()))
    return assets


def _chamadas() -> dict[str, list[tuple[str, str]]]:
    return {script.name: CHAMADA_DA_API.findall(script.read_text()) for script in UI_DIR.glob("*.js")}


def _existe_rota(metodo: str, caminho: str) -> bool:
    caminho = PARAMETRO_NO_TEMPLATE.sub(ID_DE_EXEMPLO, caminho).split("?")[0]
    return any(
        metodo.lower() in operacoes and re.fullmatch(PARAMETRO_NA_ROTA.sub("[^/]+", rota), caminho)
        for rota, operacoes in app.openapi()["paths"].items()
    )


def test_raiz_redireciona_para_a_ui(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_ui_sem_pagina_serve_a_fila(client: TestClient) -> None:
    response = client.get("/ui/")

    assert response.status_code == 200
    assert response.text == (UI_DIR / "index.html").read_text()


@pytest.mark.parametrize("pagina", PAGINAS)
def test_paginas_respondem_html(client: TestClient, pagina: str) -> None:
    response = client.get(f"/ui/{pagina}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="pt-BR">' in response.text


def test_assets_referenciados_respondem_com_o_tipo_certo(client: TestClient) -> None:
    assets = _assets()
    assert {"estilo.css", "comum.js", "fila.js", "chat.js", "politica.js"} <= assets

    for asset in sorted(assets):
        response = client.get(f"/ui/{asset}")
        assert response.status_code == 200, asset
        sufixo = asset[asset.rindex(".") :]
        assert response.headers["content-type"].startswith(TIPOS[sufixo]), asset


def test_cada_pagina_chama_a_api() -> None:
    chamadas = _chamadas()

    assert {metodo for metodo, _ in chamadas["fila.js"]} == {"GET", "POST"}
    assert ("POST", "/chat") in chamadas["chat.js"]
    assert {("GET", "/politica-compra"), ("PUT", "/politica-compra")} <= set(chamadas["politica.js"])


def test_endpoints_chamados_pelos_js_existem_no_app() -> None:
    chamadas = [(script, m, c) for script, lista in _chamadas().items() for m, c in lista]

    assert len(chamadas) >= 7
    inexistentes = [(script, m, c) for script, m, c in chamadas if not _existe_rota(m, c)]
    assert inexistentes == []


def test_rota_inexistente_nao_passa_na_conferencia() -> None:
    assert not _existe_rota("POST", "/sugestoes/${s.id}/cancelar")
    assert not _existe_rota("DELETE", "/politica-compra")
    assert _existe_rota("POST", "/sugestoes/${s.id}/aprovar")


def test_onboarding_tem_uma_opcao_por_motivo_de_destaque() -> None:
    html = (UI_DIR / "politica.html").read_text()

    opcoes = set(re.findall(r'name="motivos_de_destaque" value="([^"]+)"', html))

    assert opcoes == {m.value for m in MotivoDestaque}
