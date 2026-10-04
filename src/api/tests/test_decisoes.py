"""Testes HTTP das decisões de compra (`/skus/{sku}/decisoes`) e do efeito delas nos
avisos e no painel, com relógio injetado. Cenário em `cenario_painel.py`."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    MAIS_URGENTE,
    PISO,
    SOBRANDO,
    URGENTE,
    avisar,
    client,  # noqa: F401 (fixture)
    codigos,
    decidir,
    painel,
    preparar,
)
from src.politica_compra.schemas import PARAMETROS_V1
from src.usuarios.schemas import Usuario


def test_vou_comprar_responde_201_com_a_sugestao_do_momento(client: TestClient, usuario_logado: Usuario) -> None:
    cenario = preparar()

    decisao = decidir(client, URGENTE, "vou_comprar", quantidade=280, comentario=" Fechei com o representante. ")

    assert decisao == {
        "id": decisao["id"],
        "sku_code": URGENTE.sku_code,
        "tipo": "vou_comprar",
        "quantidade": 280,
        "motivo": None,
        "comentario": "Fechei com o representante.",
        "decidido_por": usuario_logado.nome,
        "quantidade_sugerida": 250,
        "politica_versao": 1,
        "criado_em": "2026-10-01T09:00:00Z",
    }
    assert [d.usuario_id for d in cenario.decisoes.listar(URGENTE.sku_code)] == [usuario_logado.id]


def test_decisao_guarda_a_versao_da_politica_ativa(client: TestClient) -> None:
    cenario = preparar()
    cenario.politicas.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"ciclo_compra_meses": 1.0}))

    decisao = decidir(client, SOBRANDO, "nao_comprar_agora", motivo="Estoque alto.")

    assert (decisao["quantidade_sugerida"], decisao["politica_versao"]) == (0, 2)


def test_decisoes_vem_da_mais_recente_para_a_mais_antiga(client: TestClient) -> None:
    cenario = preparar()
    primeira = decidir(client, URGENTE, "negociando")
    cenario.relogio.avancar(days=1)
    segunda = decidir(client, URGENTE, "vou_comprar", quantidade=300)

    decisoes = client.get(f"/skus/{URGENTE.sku_code}/decisoes").json()

    assert [d["id"] for d in decisoes] == [segunda["id"], primeira["id"]]
    assert client.get(f"/skus/{PISO.sku_code}/decisoes").json() == []


def test_decisao_tira_o_sku_de_alertas_e_poe_em_decididos(client: TestClient) -> None:
    preparar()

    decisao = decidir(client, URGENTE, "negociando", comentario="Representante volta sexta.")

    resultado = painel(client)
    assert URGENTE.sku_code not in codigos(resultado["alertas"])
    assert resultado["decididos"] == [
        {
            "sku_code": URGENTE.sku_code,
            "produto_nome": "Toalha Banho Conforto",
            "cor": "branco",
            "tamanho": "70x140",
            "decisao": decisao,
        }
    ]


def test_decididos_vem_da_decisao_mais_recente(client: TestClient) -> None:
    cenario = preparar()
    decidir(client, URGENTE)
    cenario.relogio.avancar(hours=1)
    decidir(client, MAIS_URGENTE)

    assert codigos(painel(client)["decididos"]) == [MAIS_URGENTE.sku_code, URGENTE.sku_code]


def test_decisao_fecha_os_avisos_abertos(client: TestClient) -> None:
    cenario = preparar()
    avisar(client, SOBRANDO)
    avisar(client, SOBRANDO, "vendendo_muito")
    cenario.relogio.avancar(minutes=30)

    decidir(client, SOBRANDO, "nao_comprar_agora", motivo="Ainda tenho 9 meses de estoque.")

    assert client.get(f"/skus/{SOBRANDO.sku_code}/avisos").json() == []
    resultado = painel(client)
    assert SOBRANDO.sku_code not in codigos(resultado["alertas"])
    assert SOBRANDO.sku_code in codigos(resultado["decididos"])


def test_aviso_posterior_a_decisao_traz_o_sku_de_volta(client: TestClient) -> None:
    cenario = preparar()
    decidir(client, URGENTE)
    cenario.relogio.avancar(days=2)

    aviso = avisar(client, URGENTE)

    resultado = painel(client)
    assert URGENTE.sku_code not in codigos(resultado["decididos"])
    urgente = next(i for i in resultado["alertas"] if i["sku_code"] == URGENTE.sku_code)
    assert urgente["avisos_abertos"] == 1
    assert urgente["ultimo_aviso"] == aviso
    assert client.get(f"/skus/{URGENTE.sku_code}/avisos").json() == [aviso]


def test_aviso_anterior_a_decisao_continua_fechado(client: TestClient) -> None:
    cenario = preparar()
    avisar(client, URGENTE)
    cenario.relogio.avancar(minutes=1)
    decidir(client, URGENTE)
    cenario.relogio.avancar(days=1)

    assert URGENTE.sku_code in codigos(painel(client)["decididos"])


@pytest.mark.parametrize(("dias", "vigente"), [(6.9, True), (7, False), (10, False)])
def test_decisao_vale_por_7_dias(client: TestClient, dias: float, vigente: bool) -> None:
    cenario = preparar()
    decidir(client, URGENTE)

    cenario.relogio.avancar(days=dias)

    resultado = painel(client)
    assert (URGENTE.sku_code in codigos(resultado["decididos"])) is vigente
    assert (URGENTE.sku_code in codigos(resultado["alertas"])) is not vigente


def test_sku_decidido_aparece_em_decididos_mesmo_sem_motivo(client: TestClient) -> None:
    cenario = preparar()
    decidir(client, SOBRANDO, "nao_comprar_agora", motivo="Estoque alto.")

    assert codigos(painel(client)["decididos"]) == [SOBRANDO.sku_code]

    cenario.relogio.avancar(days=7)

    resultado = painel(client)
    assert SOBRANDO.sku_code not in codigos(resultado["alertas"]) + codigos(resultado["decididos"])


@pytest.mark.parametrize(
    "corpo",
    [
        {"tipo": "vou_comprar"},
        {"tipo": "vou_comprar", "quantidade": 0},
        {"tipo": "vou_comprar", "quantidade": -5},
        {"tipo": "negociando", "quantidade": 100},
        {"tipo": "nao_comprar_agora"},
        {"tipo": "nao_comprar_agora", "motivo": "   "},
        {"tipo": "aprovar", "quantidade": 100},
    ],
    ids=[
        "comprar-sem-quantidade",
        "comprar-com-zero",
        "comprar-negativo",
        "quantidade-fora-do-comprar",
        "nao-comprar-sem-motivo",
        "nao-comprar-com-motivo-em-branco",
        "tipo-invalido",
    ],
)
def test_validacoes_de_cada_tipo_respondem_422_e_nao_gravam(client: TestClient, corpo: dict) -> None:
    cenario = preparar()

    response = client.post(f"/skus/{URGENTE.sku_code}/decisoes", json=corpo)

    assert response.status_code == 422
    assert cenario.decisoes.listar(URGENTE.sku_code) == []


def test_decisao_ignora_nome_no_corpo(client: TestClient, usuario_logado: Usuario) -> None:
    preparar()

    decisao = decidir(client, URGENTE, decidido_por="Outra Pessoa")

    assert decisao["decidido_por"] == usuario_logado.nome


def test_decisao_de_sku_inexistente_responde_404(client: TestClient) -> None:
    preparar()

    response = client.post("/skus/NAO-EXISTE/decisoes", json={"tipo": "negociando"})

    assert response.status_code == 404
    assert client.get("/skus/NAO-EXISTE/decisoes").status_code == 404


def test_decisao_nao_cria_pedido_de_compra(client: TestClient) -> None:
    cenario = preparar()
    pedidos_antes = list(cenario.erp.pedidos_compra)

    decidir(client, URGENTE, "vou_comprar", quantidade=300)

    assert cenario.erp.pedidos_compra == pedidos_antes
