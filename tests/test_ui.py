"""Testes HTTP da UI estática em `/ui` e dos endpoints que os `.js` chamam."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from src.main import UI_DIR, app
from src.politica_compra.schemas import MotivoAlerta

PAGINAS = [
    "index.html",
    "sku.html",
    "aviso.html",
    "politica.html",
    "login.html",
    "usuarios.html",
    "conta.html",
    "estoque.html",
]
PAPEL_DAS_PAGINAS = {
    "index.html": "comprador",
    "sku.html": "comprador",
    "politica.html": "comprador",
    "estoque.html": "comprador",
    "aviso.html": "vendas",
    "usuarios.html": "admin",
}
PAGINAS_DO_COMPRADOR = {
    "index.html": "painel.js",
    "sku.html": "sku.js",
    "politica.html": "politica.js",
    "estoque.html": "estoque.js",
}
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
    assert {
        "estilo.css",
        "comum.js",
        "painel.js",
        "sku.js",
        "aviso.js",
        "chat.js",
        "politica.js",
        "login.js",
        "usuarios.js",
        "conta.js",
        "estoque.js",
        "notificacoes.js",
    } <= assets

    for asset in sorted(assets):
        response = client.get(f"/ui/{asset}")
        assert response.status_code == 200, asset
        sufixo = asset[asset.rindex(".") :]
        assert response.headers["content-type"].startswith(TIPOS[sufixo]), asset


def test_cada_pagina_chama_a_api() -> None:
    chamadas = _chamadas()

    assert {("GET", "/painel?${consulta}"), ("GET", "/categorias"), ("GET", "/fornecedores")} <= set(
        chamadas["painel.js"]
    )
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
    assert chamadas["login.js"] == [("POST", "/login")]
    assert {("GET", "/eu"), ("POST", "/logout")} <= set(chamadas["comum.js"])
    assert set(chamadas["usuarios.js"]) == {
        ("GET", "/usuarios"),
        ("POST", "/usuarios"),
        ("PUT", "/usuarios/${pessoa.id}/papeis"),
        ("POST", "/usuarios/${pessoa.id}/desativar"),
        ("POST", "/usuarios/${pessoa.id}/reativar"),
        ("PUT", "/usuarios/${pessoa.id}/senha"),
    }
    assert chamadas["conta.js"] == [("PUT", "/eu/senha")]
    assert set(chamadas["notificacoes.js"]) == {("GET", "/notificacoes"), ("POST", "/notificacoes/vistas")}
    assert set(chamadas["estoque.js"]) == {("GET", "/estoque?${consulta}"), ("GET", "/categorias")}


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


def test_pagina_de_aviso_nao_tem_chat() -> None:
    html = (UI_DIR / "aviso.html").read_text()

    assert "chat" not in html.lower()
    assert 'name="viewport"' in html


def test_painel_tem_link_para_a_pagina_de_aviso_e_nao_tem_mais_o_link_publico() -> None:
    html = (UI_DIR / "index.html").read_text()

    assert 'href="aviso.html"' in html
    assert "copiar" not in html.lower() + (UI_DIR / "painel.js").read_text().lower()


def test_aviso_e_decisao_nao_pedem_mais_o_nome() -> None:
    for pagina, script, campo in [("aviso.html", "aviso.js", "avisado_por"), ("sku.html", "sku.js", "decidido_por:")]:
        assert "Seu nome" not in (UI_DIR / pagina).read_text()
        js = (UI_DIR / script).read_text()
        assert campo not in js and "lerNome" not in js and "guardarNome" not in js
    assert "localStorage" not in (UI_DIR / "comum.js").read_text()


def test_conta_monta_o_cabecalho_de_qualquer_papel_e_o_nome_leva_a_ela() -> None:
    assert re.search(r"<nav[^>]*></nav>", (UI_DIR / "conta.html").read_text())
    assert "cabecalho()" in (UI_DIR / "conta.js").read_text()
    assert 'href: "conta.html"' in (UI_DIR / "comum.js").read_text()


def test_linhas_do_painel_abrem_a_tela_do_sku() -> None:
    assert "sku.html?sku=" in (UI_DIR / "painel.js").read_text()


def test_painel_tem_busca_e_filtros_com_os_nomes_da_api_e_guarda_na_url() -> None:
    html = (UI_DIR / "index.html").read_text()
    painel = (UI_DIR / "painel.js").read_text()
    parametros = {p["name"] for p in app.openapi()["paths"]["/painel"]["get"]["parameters"] if p["in"] == "query"}
    campos = set(re.findall(r'<(?:input|select) id="filtro-\w+" name="(\w+)"', html))

    assert campos == parametros == {"busca", "categoria", "motivo", "fornecedor"}
    assert 'id="limpar-filtros"' in html
    assert "barraDeFiltros(" in painel and "guardarNaUrl(" in painel
    assert "Nenhum SKU com esses filtros" in painel and "Tudo em dia" in painel


def test_barra_de_filtros_guarda_os_filtros_na_url() -> None:
    comum = (UI_DIR / "comum.js").read_text()

    assert "history.replaceState" in comum and "location.search" in comum


def test_estoque_tem_a_barra_de_filtros_do_painel_com_os_nomes_da_api() -> None:
    html = (UI_DIR / "estoque.html").read_text()
    estoque = (UI_DIR / "estoque.js").read_text()
    parametros = {p["name"] for p in app.openapi()["paths"]["/estoque"]["get"]["parameters"] if p["in"] == "query"}
    campos = set(re.findall(r'<(?:input|select) id="[\w-]+" name="(\w+)"', html))

    assert campos == {"busca", "categoria", "situacao", "ordem"}
    assert campos | {"pagina", "por_pagina"} == parametros
    assert 'id="limpar-filtros"' in html
    assert "barraDeFiltros(" in estoque and "guardarNaUrl(" in estoque
    assert {"em_ruptura", "sem_venda", "com_transito"} <= set(re.findall(r'\["(\w+)", "', estoque))
    assert "sku.html?sku=" in estoque
    assert "Nenhum SKU com esses filtros" in estoque


def test_menu_do_comprador_tem_o_estoque_logo_depois_do_painel() -> None:
    telas = re.findall(r'\{ papel: "(\w+)", href: "([^"]+)"', (UI_DIR / "comum.js").read_text())

    assert telas[:2] == [("comprador", "index.html"), ("comprador", "estoque.html")]


def test_decididos_ficam_recolhidos_por_padrao() -> None:
    painel = (UI_DIR / "painel.js").read_text()

    assert "Decididos nos últimos 7 dias" in painel
    assert re.search(r'"details",\s*\{ class: "card decididos"[^}]*\}', painel)


def test_chat_html_saiu(client: TestClient) -> None:
    assert client.get("/ui/chat.html").status_code == 404


@pytest.mark.parametrize(("pagina", "script"), PAGINAS_DO_COMPRADOR.items())
def test_telas_do_comprador_tem_o_chat_lateral(pagina: str, script: str) -> None:
    assert 'id="abrir-chat"' in (UI_DIR / pagina).read_text()
    assert re.search(r"montarChat\(", (UI_DIR / script).read_text())


@pytest.mark.parametrize(("pagina", "papel"), PAPEL_DAS_PAGINAS.items())
def test_cada_tela_monta_o_cabecalho_do_seu_papel(pagina: str, papel: str) -> None:
    html = (UI_DIR / pagina).read_text()
    script = re.findall(r'<script type="module" src="([^"]+)"', html)[0]

    assert re.search(r"<nav[^>]*></nav>", html)
    assert f'cabecalho("{papel}")' in (UI_DIR / script).read_text()


def test_o_menu_so_aponta_para_telas_que_existem() -> None:
    telas = re.findall(r'\{ papel: "(\w+)", href: "([^"]+)"', (UI_DIR / "comum.js").read_text())

    assert ("comprador", "index.html") == telas[0]
    assert ("vendas", "aviso.html") in telas
    assert ("admin", "usuarios.html") in telas
    assert all((UI_DIR / href).exists() for _, href in telas)


def test_api_manda_x_requested_with_e_leva_ao_login_no_401() -> None:
    comum = (UI_DIR / "comum.js").read_text()

    assert '"X-Requested-With"' in comum
    assert "resposta.status === 401" in comum and "login.html" in comum and "volta=" in comum


def test_pagina_de_login_nao_monta_cabecalho() -> None:
    html = (UI_DIR / "login.html").read_text()

    assert "<nav" not in html and 'type="password"' in html
    assert "cabecalho(" not in (UI_DIR / "login.js").read_text()


def test_tela_do_sku_passa_o_sku_em_contexto_ao_chat() -> None:
    assert "montarChat(skuCode" in (UI_DIR / "sku.js").read_text()
    assert "sku_code: skuEmContexto" in (UI_DIR / "chat.js").read_text()
