"""Testes HTTP do acompanhamento da vendedora: `/avisos/meus` mostra os avisos dela dos
últimos 30 dias com a decisão de compra que fechou cada um, e a decisão notifica a autora
de cada aviso aberto. Cenário em `cenario_painel.py`: hoje é 01/10/2026, 9h. Cada pessoa
entra pelo `como`, lida do repositório em memória a cada requisição, como a sessão faz."""
from __future__ import annotations

import json
from datetime import date

from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    BOA_VISTA,
    REGULAR,
    URGENTE,
    ZERADO,
    Cenario,
    atrasar,
    avisar,
    client,  # noqa: F401 (fixture)
    decidir,
    preparar,
)
from src.main import app
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Usuario
from tests.fakes import make_usuario

BIA = make_usuario("Bia", papeis=["vendas"])
ANA = make_usuario("Ana", papeis=["vendas"])
LIA = make_usuario("Lia", papeis=["vendas"])
CARLA = make_usuario("Carla", papeis=["comprador"])


def como(cenario: Cenario, usuario: Usuario) -> None:
    if cenario.usuarios.por_id(usuario.id) is None:
        cenario.usuarios.gravar(usuario)
    app.dependency_overrides[usuario_atual] = lambda: cenario.usuarios.por_id(usuario.id)


def meus_avisos(client: TestClient) -> list[dict]:
    response = client.get("/avisos/meus")
    assert response.status_code == 200, response.text
    return response.json()


def decisoes_notificadas(client: TestClient) -> list[dict]:
    response = client.get("/notificacoes")
    assert response.status_code == 200, response.text
    return [n for n in response.json()["notificacoes"] if n["tipo"] == "decisao_sobre_aviso"]


def test_a_decisao_notifica_a_autora_de_cada_aviso_aberto_e_mais_ninguem(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, ZERADO, "acabou")
    como(cenario, ANA)
    avisar(client, ZERADO, "vendendo_muito")
    cenario.relogio.avancar(minutes=30)
    como(cenario, CARLA)
    decidir(client, ZERADO, "vou_comprar", quantidade=120)

    como(cenario, BIA)
    [notificacao] = decisoes_notificadas(client)
    assert notificacao["sku_code"] == ZERADO.sku_code
    assert notificacao["aberto_em"] == "2026-10-01T09:30:00Z"
    assert notificacao["lida"] is False
    assert notificacao["detalhe"] == {
        "produto_nome": "Toalha Banho Conforto",
        "cor": "lilás",
        "tamanho": "70x140",
        "tipo": "vou_comprar",
        "quantidade": 120,
        "motivo": None,
        "decidido_por": "Carla",
    }
    como(cenario, ANA)
    assert len(decisoes_notificadas(client)) == 1
    como(cenario, LIA)
    assert decisoes_notificadas(client) == []
    como(cenario, CARLA)
    assert decisoes_notificadas(client) == []


def test_dois_avisos_da_mesma_vendedora_no_mesmo_sku_notificam_uma_vez(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, ZERADO, "acabou")
    avisar(client, ZERADO, "vendendo_muito")
    como(cenario, CARLA)
    decidir(client, ZERADO, "negociando")

    como(cenario, BIA)
    assert len(decisoes_notificadas(client)) == 1


def test_decisao_sem_aviso_aberto_nao_notifica_a_vendedora(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, ZERADO, "acabou")
    como(cenario, CARLA)
    decidir(client, ZERADO, "negociando")
    cenario.relogio.avancar(days=1)
    decidir(client, ZERADO, "vou_comprar", quantidade=50)
    decidir(client, REGULAR, "negociando")

    como(cenario, BIA)
    assert [n["detalhe"]["tipo"] for n in decisoes_notificadas(client)] == ["negociando"]


def test_meus_avisos_mostra_a_decisao_que_fechou_cada_um_ou_que_aguarda_o_comprador(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    primeiro = avisar(client, ZERADO, "acabou", comentario="Cliente quer 200.")
    cenario.relogio.avancar(hours=1)
    segundo = avisar(client, URGENTE, "vendendo_muito")
    cenario.relogio.avancar(hours=1)
    como(cenario, CARLA)
    decidir(client, ZERADO, "vou_comprar", quantidade=120, comentario="Paguei R$ 20,00 da última vez.")
    cenario.relogio.avancar(hours=1)
    decidir(client, ZERADO, "negociando")

    como(cenario, BIA)
    assert meus_avisos(client) == [
        {
            "id": segundo["id"],
            "para": "comprador",
            "sku_code": URGENTE.sku_code,
            "produto_nome": "Toalha Banho Conforto",
            "cor": "branco",
            "tamanho": "70x140",
            "tipo": "vendendo_muito",
            "comentario": None,
            "criado_em": "2026-10-01T10:00:00Z",
            "decisao": None,
        },
        {
            "id": primeiro["id"],
            "para": "comprador",
            "sku_code": ZERADO.sku_code,
            "produto_nome": "Toalha Banho Conforto",
            "cor": "lilás",
            "tamanho": "70x140",
            "tipo": "acabou",
            "comentario": "Cliente quer 200.",
            "criado_em": "2026-10-01T09:00:00Z",
            "decisao": {
                "tipo": "vou_comprar",
                "quantidade": 120,
                "motivo": None,
                "criado_em": "2026-10-01T11:00:00Z",
            },
        },
    ]


def test_nao_comprar_agora_mostra_o_motivo(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, REGULAR, "vendendo_muito")
    como(cenario, CARLA)
    decidir(client, REGULAR, "nao_comprar_agora", motivo="Estoque segura 45 dias.")

    como(cenario, BIA)
    [aviso] = meus_avisos(client)
    assert aviso["decisao"] == {
        "tipo": "nao_comprar_agora",
        "quantidade": None,
        "motivo": "Estoque segura 45 dias.",
        "criado_em": "2026-10-01T09:00:00Z",
    }


def test_meus_avisos_mostra_so_os_da_propria_vendedora(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, ZERADO, "acabou")
    como(cenario, ANA)
    avisar(client, URGENTE, "acabou")

    como(cenario, BIA)
    assert [a["sku_code"] for a in meus_avisos(client)] == [ZERADO.sku_code]
    como(cenario, LIA)
    assert meus_avisos(client) == []


def test_meus_avisos_mostra_so_os_ultimos_30_dias(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar(client, ZERADO, "acabou")
    cenario.relogio.avancar(days=1)
    avisar(client, URGENTE, "acabou")

    cenario.relogio.avancar(days=29, minutes=1)

    assert [a["sku_code"] for a in meus_avisos(client)] == [URGENTE.sku_code]


def test_nenhuma_rota_da_vendedora_devolve_preco_de_compra_nem_fornecedor(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (ZERADO, 30), prevista=date(2026, 9, 25))
    como(cenario, CARLA)
    assert client.post(f"/pedidos/{pedido.id}/cobrancas", json={"nova_previsao": "2026-10-15"}).status_code == 201
    como(cenario, BIA)
    respostas = [
        client.get("/skus", params={"busca": "toalha lilás"}),
        client.get(f"/skus/{ZERADO.sku_code}/disponibilidade"),
        client.post("/avisos", json={"sku_code": ZERADO.sku_code, "tipo": "acabou"}),
    ]
    como(cenario, CARLA)
    decidir(client, ZERADO, "vou_comprar", quantidade=120, comentario="Boa Vista fez R$ 20,00 a unidade.")
    como(cenario, BIA)
    respostas += [client.get("/avisos/meus"), client.get("/notificacoes"), client.get("/eu")]

    assert [r.status_code for r in respostas] == [200, 200, 201, 200, 200, 200]
    for resposta in respostas:
        texto = json.dumps(resposta.json(), ensure_ascii=False).lower()
        for proibido in ("preco", "preço", "fornecedor", "boa vista", "katrina", "r$", "quantidade_sugerida"):
            assert proibido not in texto, (resposta.url, proibido)
