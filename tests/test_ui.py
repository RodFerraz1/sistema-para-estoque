"""Testes HTTP da UI estática em `/ui` e dos endpoints que os `.js` chamam."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.main import UI_DIR, app
from src.politica_compra.schemas import MotivoAlerta

PAGINAS = ["index.html", "sku.html", "aviso.html", "politica.html"]
PAGINAS_DO_COMPRADOR = {"index.html": "painel.js", "sku.html": "sku.js", "politica.html": "politica.js"}
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


def test_ui_sem_pagina_serve_o_painel(client: TestClient) -> None:
    response = client.get("/ui/")

    assert response.status_code == 200
    assert response.text == (UI_DIR / "index.html").read_text()


@pytest.mark.parametrize("pagina", PAGINAS)
def test_paginas_respondem_html(client: TestClient, pagina: str) -> None:
    response = client.get(f"/ui/{pagina}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="pt-BR">' in response.text


@pytest.mark.parametrize("arquivo", ["", "index.html", "estilo.css", "painel.js"])
def test_ui_pede_ao_navegador_para_revalidar_sempre(client: TestClient, arquivo: str) -> None:
    response = client.get(f"/ui/{arquivo}")

    assert response.headers["cache-control"] == "no-cache"


def test_assets_referenciados_respondem_com_o_tipo_certo(client: TestClient) -> None:
    assets = _assets()
    assert {"estilo.css", "comum.js", "painel.js", "sku.js", "aviso.js", "chat.js", "politica.js"} <= assets

    for asset in sorted(assets):
        response = client.get(f"/ui/{asset}")
        assert response.status_code == 200, asset
        sufixo = asset[asset.rindex(".") :]
        assert response.headers["content-type"].startswith(TIPOS[sufixo]), asset


def test_cada_pagina_chama_a_api() -> None:
    chamadas = _chamadas()

    assert ("GET", "/painel") in chamadas["painel.js"]
    assert {metodo for metodo, _ in chamadas["aviso.js"]} == {"GET", "POST"}
    assert ("POST", "/skus/${sku}/decisoes") in chamadas["sku.js"]
    assert {caminho.split("/")[-1].split("?")[0] for _, caminho in chamadas["sku.js"]} >= {
        "analise",
        "avisos",
        "decisoes",
        "sugestao-compra",
        "sinais",
        "precos",
        "vendas",
    }
    assert ("POST", "/chat") in chamadas["chat.js"]
    assert {("GET", "/politica-compra"), ("PUT", "/politica-compra")} <= set(chamadas["politica.js"])


def test_endpoints_chamados_pelos_js_existem_no_app() -> None:
    chamadas = [(script, m, c) for script, lista in _chamadas().items() for m, c in lista]

    assert len(chamadas) >= 3
    inexistentes = [(script, m, c) for script, m, c in chamadas if not _existe_rota(m, c)]
    assert inexistentes == []


def test_rota_inexistente_nao_passa_na_conferencia() -> None:
    assert not _existe_rota("POST", "/sugestoes/${s.id}/aprovar")
    assert not _existe_rota("DELETE", "/politica-compra")
    assert _existe_rota("GET", "/skus/${sku}/sugestao-compra")


def test_onboarding_tem_uma_opcao_por_motivo_de_alerta() -> None:
    html = (UI_DIR / "politica.html").read_text()

    opcoes = set(re.findall(r'name="motivos_de_alerta" value="([^"]+)"', html))

    assert opcoes == {m.value for m in MotivoAlerta}


def test_politica_nao_tem_faixa_de_aprovacao() -> None:
    assert "faixa" not in (UI_DIR / "politica.html").read_text() + (UI_DIR / "politica.js").read_text()


def test_pagina_de_aviso_nao_tem_navegacao_nem_chat() -> None:
    html = (UI_DIR / "aviso.html").read_text()

    assert "<nav" not in html
    assert "chat" not in html.lower()
    assert 'name="viewport"' in html


def test_painel_tem_link_para_a_pagina_de_aviso() -> None:
    assert 'href="aviso.html"' in (UI_DIR / "index.html").read_text()


def test_linhas_do_painel_abrem_a_tela_do_sku() -> None:
    assert "sku.html?sku=" in (UI_DIR / "painel.js").read_text()


def test_decididos_ficam_recolhidos_por_padrao() -> None:
    painel = (UI_DIR / "painel.js").read_text()

    assert "Decididos nos últimos 7 dias" in painel
    assert re.search(r'"details",\s*\{ class: "card decididos"[^}]*\}', painel)


def test_chat_html_saiu(client: TestClient) -> None:
    assert client.get("/ui/chat.html").status_code == 404


@pytest.mark.parametrize(("pagina", "script"), PAGINAS_DO_COMPRADOR.items())
def test_telas_do_comprador_tem_o_chat_lateral_e_navegacao_painel_e_politica(pagina: str, script: str) -> None:
    html = (UI_DIR / pagina).read_text()

    assert re.findall(r'<nav>(.*?)</nav>', html, re.S)[0].count("<a ") == 2
    assert 'href="index.html"' in html and 'href="politica.html"' in html
    assert 'id="abrir-chat"' in html
    assert re.search(r"montarChat\(", (UI_DIR / script).read_text())


def test_tela_do_sku_passa_o_sku_em_contexto_ao_chat() -> None:
    assert "montarChat(skuCode" in (UI_DIR / "sku.js").read_text()
    assert "sku_code: skuEmContexto" in (UI_DIR / "chat.js").read_text()
