"""Testes HTTP da verificação de gôndola (`/skus/{sku}/verificacoes`): a saída e a volta do
painel do repositor, o estoque divergente no painel do comprador e as notificações de queda
de venda e de estoque divergente.

Mesmo cenário do `test_reposicao.py`: o relógio começa na segunda-feira às 9h, a janela
observada é sexta e sábado e o tapete marrom vendia 10 por dia e vendeu 5 e 0, com 400 no
ERP. `abrir_o_dia` fecha o dia de hoje com a `LOJA` vendendo (e os SKUs que o teste pedir) e
leva o relógio para as 9h do dia seguinte.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import DEPENDENCIAS, Cenario, codigos, decidir, painel
from src.api.tests.test_reposicao import (
    AGORA,
    LOJA,
    REGULAR,
    TAPETE,
    painel_do_repositor,
    preparar_reposicao,
    vendas,
)
from src.catalog.schemas import SKU
from src.main import app
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Papel
from tests.fakes import make_estoque, make_sku, make_usuario, make_venda


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def preparar(disponiveis: dict[str, int] | None = None, **parametros: object) -> Cenario:
    return preparar_reposicao(
        {TAPETE.sku_code: 400, **(disponiveis or {})},
        vendas(TAPETE, 10, 5, 0),
        **parametros,
    )


def abrir_o_dia(cenario: Cenario, *vendidos: tuple[SKU, int]) -> None:
    quando = datetime.combine(cenario.relogio.agora.date(), time(15), tzinfo=UTC)
    for sku, quantidade in [(LOJA, 6), *vendidos]:
        cenario.erp.vendas.append(make_venda(sku, quando, quantidade, key=f"{sku.sku_code}-{quando:%F}"))
    cenario.relogio.agora = datetime.combine(quando.date() + timedelta(days=1), time(9), tzinfo=UTC)


def mudar_o_disponivel(cenario: Cenario, sku: SKU, disponivel: int) -> None:
    cenario.erp.estoques_por_sku[sku.sku_code] = make_estoque(disponivel=disponivel)


def verificar(client: TestClient, sku: SKU, resultado: str, **campos: object) -> dict:
    response = client.post(f"/skus/{sku.sku_code}/verificacoes", json={"resultado": resultado, **campos})
    assert response.status_code == 201, response.text
    return response.json()


def do_comprador(client: TestClient, sku: SKU) -> dict | None:
    return next((i for i in painel(client)["alertas"] if i["sku_code"] == sku.sku_code), None)


def notificacoes(client: TestClient, tipo: str) -> list[dict]:
    response = client.get("/notificacoes")
    assert response.status_code == 200, response.text
    return [n for n in response.json()["notificacoes"] if n["tipo"] == tipo]


@pytest.mark.papeis("reposicao")
def test_a_verificacao_grava_o_que_o_repositor_achou_com_o_disponivel_e_quem_verificou(client: TestClient) -> None:
    preparar()

    criada = verificar(client, TAPETE, "estava_na_gondola", comentario="  Estava no lugar errado.  ")

    assert criada["sku_code"] == TAPETE.sku_code
    assert criada["resultado"] == "estava_na_gondola"
    assert criada["comentario"] == "Estava no lugar errado."
    assert criada["disponivel_no_erp"] == 400
    assert criada["verificado_por"] == "Pessoa Teste"
    assert criada["criado_em"] == AGORA.isoformat().replace("+00:00", "Z")


def test_o_historico_vem_da_verificacao_mais_recente_para_a_mais_antiga(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "repus")
    cenario.relogio.avancar(hours=2)
    verificar(client, TAPETE, "sem_estoque_no_deposito", comentario="Nem no fundo do depósito.")

    response = client.get(f"/skus/{TAPETE.sku_code}/verificacoes")

    assert response.status_code == 200
    assert [(v["resultado"], v["comentario"]) for v in response.json()] == [
        ("sem_estoque_no_deposito", "Nem no fundo do depósito."),
        ("repus", None),
    ]
    assert client.get(f"/skus/{REGULAR.sku_code}/verificacoes").json() == []


def test_sku_desconhecido_responde_404_e_inativo_422(client: TestClient) -> None:
    cenario = preparar()
    cenario.erp.skus.append(make_sku("PM-VERM-140-01", ativo=False))
    cenario.erp.estoques_por_sku["PM-VERM-140-01"] = make_estoque(disponivel=3)

    assert client.post("/skus/NAO-EXISTE/verificacoes", json={"resultado": "repus"}).status_code == 404
    assert client.get("/skus/NAO-EXISTE/verificacoes").status_code == 404
    assert client.post("/skus/PM-VERM-140-01/verificacoes", json={"resultado": "repus"}).status_code == 422


def test_resultado_fora_da_lista_responde_422(client: TestClient) -> None:
    preparar()

    response = client.post(f"/skus/{TAPETE.sku_code}/verificacoes", json={"resultado": "sumiu"})

    assert response.status_code == 422


@pytest.mark.parametrize("papel", ["comprador", "vendas", "admin"])
def test_so_o_repositor_registra_verificacao(client: TestClient, papel: Papel) -> None:
    preparar()
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert client.post(f"/skus/{TAPETE.sku_code}/verificacoes", json={"resultado": "repus"}).status_code == 403


@pytest.mark.parametrize(("papel", "status"), [("comprador", 200), ("reposicao", 200), ("vendas", 403), ("admin", 403)])
def test_o_comprador_e_o_repositor_veem_as_verificacoes(client: TestClient, papel: Papel, status: int) -> None:
    preparar()
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert client.get(f"/skus/{TAPETE.sku_code}/verificacoes").status_code == status


@pytest.mark.parametrize("resultado", ["repus", "estava_na_gondola", "sem_estoque_no_deposito"])
def test_a_verificacao_do_dia_tira_o_sku_do_painel_do_repositor(client: TestClient, resultado: str) -> None:
    preparar()

    verificar(client, TAPETE, resultado)

    assert painel_do_repositor(client) == []


def test_o_sku_verificado_volta_quando_um_dia_aberto_inteiro_fecha_ainda_parado(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "repus")

    abrir_o_dia(cenario)
    assert painel_do_repositor(client) == [], "a segunda da verificação não é um dia inteiro depois dela"

    abrir_o_dia(cenario)
    [tapete] = painel_do_repositor(client)
    assert tapete["sku_code"] == TAPETE.sku_code
    assert [d["quantidade"] for d in tapete["ultimos_dias"]] == [0, 0]


def test_o_sku_verificado_que_voltou_a_vender_nao_volta(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "repus")

    abrir_o_dia(cenario, (TAPETE, 9))
    abrir_o_dia(cenario, (TAPETE, 11))

    assert painel_do_repositor(client) == []


def test_domingo_sem_venda_nao_conta_como_dia_inteiro_depois_da_verificacao(client: TestClient) -> None:
    cenario = preparar()
    cenario.relogio.agora -= timedelta(days=2)
    verificar(client, TAPETE, "repus")
    cenario.relogio.agora = AGORA

    assert painel_do_repositor(client) == []


def test_sem_estoque_no_deposito_poe_o_sku_em_estoque_divergente_no_painel_do_comprador(client: TestClient) -> None:
    preparar()

    verificar(client, TAPETE, "sem_estoque_no_deposito", comentario="Procurei no depósito todo.")

    item = do_comprador(client, TAPETE)
    assert item is not None
    assert item["grupo"] == "estoque_divergente"
    assert item["motivos"] == ["estoque_divergente"]
    assert item["disponivel"] == 400
    verificacao = item["estoque_divergente"]
    assert (verificacao["verificado_por"], verificacao["disponivel_no_erp"]) == ("Pessoa Teste", 400)
    assert verificacao["comentario"] == "Procurei no depósito todo."
    assert painel(client)["contagens"]["estoque_divergente"] == 1


@pytest.mark.parametrize("resultado", ["repus", "estava_na_gondola"])
def test_achar_a_mercadoria_nao_e_estoque_divergente(client: TestClient, resultado: str) -> None:
    preparar()

    verificar(client, TAPETE, resultado)

    assert do_comprador(client, TAPETE) is None


def test_sem_estoque_no_deposito_com_o_erp_zerado_nao_e_estoque_divergente(client: TestClient) -> None:
    preparar({TAPETE.sku_code: 0})

    verificar(client, TAPETE, "sem_estoque_no_deposito")

    item = do_comprador(client, TAPETE)
    assert item is not None
    assert "estoque_divergente" not in item["motivos"]
    assert item["estoque_divergente"] is None


def test_uma_verificacao_posterior_que_achou_a_mercadoria_desfaz_o_estoque_divergente(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito")
    cenario.relogio.avancar(hours=3)

    verificar(client, TAPETE, "repus", comentario="Achei atrás das caixas.")

    assert do_comprador(client, TAPETE) is None


def test_a_decisao_de_compra_tira_o_estoque_divergente_mesmo_depois_de_vencer(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito")
    cenario.relogio.avancar(hours=1)

    decidir(client, TAPETE, "vou_comprar", quantidade=100)

    resultado = painel(client)
    assert TAPETE.sku_code not in codigos(resultado["alertas"])
    assert TAPETE.sku_code in codigos(resultado["decididos"])
    cenario.relogio.avancar(days=8)
    assert do_comprador(client, TAPETE) is None


def test_o_disponivel_do_erp_mudar_tira_o_estoque_divergente(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito")

    mudar_o_disponivel(cenario, TAPETE, 0)

    item = do_comprador(client, TAPETE)
    assert item is None or "estoque_divergente" not in item["motivos"]


def test_com_o_motivo_desligado_o_estoque_divergente_nao_aparece(client: TestClient) -> None:
    preparar(motivos_de_alerta=("abaixo_do_piso_alerta", "entrega_atrasada"))

    verificar(client, TAPETE, "sem_estoque_no_deposito")

    assert do_comprador(client, TAPETE) is None


def test_o_filtro_por_motivo_traz_so_o_estoque_divergente(client: TestClient) -> None:
    preparar({LOJA.sku_code: 0})
    verificar(client, TAPETE, "sem_estoque_no_deposito")
    assert LOJA.sku_code in codigos(painel(client)["alertas"])

    response = client.get("/painel", params={"motivo": "estoque_divergente"})

    assert codigos(response.json()["alertas"]) == [TAPETE.sku_code]


def test_o_repositor_e_notificado_do_sku_novo_na_lista_uma_vez(client: TestClient) -> None:
    preparar()

    [queda] = notificacoes(client, "queda_de_venda")
    assert notificacoes(client, "queda_de_venda") == [queda]

    assert queda["sku_code"] == TAPETE.sku_code
    assert queda["fechado_em"] is None
    assert queda["detalhe"]["produto_nome"] == "Tapete Banheiro"
    assert queda["detalhe"]["disponivel"] == 400
    assert queda["detalhe"]["venda_diaria_base"] == pytest.approx(10)
    assert queda["detalhe"]["vendido_na_janela"] == 5


@pytest.mark.papeis("comprador")
def test_o_comprador_nao_recebe_a_queda_de_venda(client: TestClient) -> None:
    preparar()

    assert notificacoes(client, "queda_de_venda") == []


def test_o_sku_verificado_no_dia_nao_notifica_e_volta_a_notificar_quando_volta(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "repus")

    assert notificacoes(client, "queda_de_venda") == []

    abrir_o_dia(cenario)
    abrir_o_dia(cenario)
    assert [n["fechado_em"] for n in notificacoes(client, "queda_de_venda")] == [None]


def test_a_verificacao_fecha_a_notificacao_da_queda_de_venda(client: TestClient) -> None:
    preparar()
    notificacoes(client, "queda_de_venda")

    verificar(client, TAPETE, "estava_na_gondola")

    [queda] = notificacoes(client, "queda_de_venda")
    assert queda["fechado_em"] is not None


def test_o_comprador_e_notificado_do_estoque_divergente(client: TestClient) -> None:
    preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito", comentario="Procurei no depósito todo.")

    [divergente] = notificacoes(client, "estoque_divergente")

    assert divergente["sku_code"] == TAPETE.sku_code
    assert divergente["fechado_em"] is None
    assert divergente["detalhe"]["disponivel_no_erp"] == 400
    assert divergente["detalhe"]["verificado_por"] == "Pessoa Teste"
    assert divergente["detalhe"]["cor"] == "marrom"


def test_a_decisao_de_compra_fecha_a_notificacao_do_estoque_divergente(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito")
    notificacoes(client, "estoque_divergente")
    cenario.relogio.avancar(hours=1)

    decidir(client, TAPETE, "negociando")

    [divergente] = notificacoes(client, "estoque_divergente")
    assert divergente["fechado_em"] is not None


def test_o_disponivel_mudar_fecha_a_notificacao_do_estoque_divergente(client: TestClient) -> None:
    cenario = preparar()
    verificar(client, TAPETE, "sem_estoque_no_deposito")
    notificacoes(client, "estoque_divergente")

    mudar_o_disponivel(cenario, TAPETE, 380)

    [divergente] = notificacoes(client, "estoque_divergente")
    assert divergente["fechado_em"] is not None
