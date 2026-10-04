"""Testes HTTP do aviso de gôndola vazia (`/avisos-gondola`): o topo do painel do repositor,
a notificação do papel `reposicao`, a verificação que fecha o aviso e notifica a vendedora,
o setor conhecido do SKU, o filtro por setor, o estoque divergente e "Meus avisos".

Mesmo cenário do `test_reposicao.py`: o relógio começa na segunda-feira às 9h e o tapete
marrom vendia 10 por dia e vendeu 5 e 0 na sexta e no sábado, com 400 no ERP. O tapete cinza
e o pano de mesa raro vendem normalmente. Cada pessoa entra pelo `como`.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import DEPENDENCIAS, Cenario, avisar, decidir, painel
from src.api.tests.test_meus_avisos import como, meus_avisos
from src.api.tests.test_reposicao import (
    AGORA,
    RARO,
    TAPETE,
    TAPETE_CINZA,
    ZERADO,
    preparar_reposicao,
    vendas,
)
from src.catalog.schemas import SKU
from src.main import app
from src.reposicao.schemas import Setor, SetorDoSku
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Papel
from tests.fakes import make_estoque, make_sku, make_usuario

BIA = make_usuario("Bia", papeis=["vendas"])
ANA = make_usuario("Ana", papeis=["vendas"])
RAFA = make_usuario("Rafa", papeis=["reposicao"])
CARLA = make_usuario("Carla", papeis=["comprador"])
TAPETES = Setor(id=uuid4(), nome="Tapetes", ativo=True)
MESA = Setor(id=uuid4(), nome="Mesa", ativo=True)
COZINHA = Setor(id=uuid4(), nome="Cozinha", ativo=False)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def preparar(disponiveis: dict[str, int] | None = None) -> Cenario:
    cenario = preparar_reposicao(
        {TAPETE.sku_code: 400, **(disponiveis or {})},
        vendas(TAPETE, 10, 5, 0),
        vendas(TAPETE_CINZA, 3, 3, 3),
        vendas(RARO, 2, 2, 2),
    )
    for setor in (TAPETES, MESA, COZINHA):
        cenario.setores.gravar(setor)
    return cenario


def iso(quando: datetime) -> str:
    return quando.isoformat().replace("+00:00", "Z")


def conhecer_o_setor(cenario: Cenario, sku: SKU, setor: Setor) -> None:
    cenario.setores.lembrar(
        SetorDoSku(sku_code=sku.sku_code, setor_id=setor.id, atualizado_em=cenario.relogio.agora, usuario_id=None)
    )


def avisar_gondola(client: TestClient, sku: SKU, setor: Setor = TAPETES, **campos: object) -> dict:
    response = client.post("/avisos-gondola", json={"sku_code": sku.sku_code, "setor_id": str(setor.id), **campos})
    assert response.status_code == 201, response.text
    return response.json()


def verificar(client: TestClient, sku: SKU, resultado: str, **campos: object) -> dict:
    response = client.post(f"/skus/{sku.sku_code}/verificacoes", json={"resultado": resultado, **campos})
    assert response.status_code == 201, response.text
    return response.json()


def do_repositor(client: TestClient, **filtros: str) -> dict:
    response = client.get("/reposicao/painel", params=filtros)
    assert response.status_code == 200, response.text
    return response.json()


def codigos(itens: list[dict]) -> list[str]:
    return [i["sku_code"] for i in itens]


def notificacoes(client: TestClient, tipo: str) -> list[dict]:
    response = client.get("/notificacoes")
    assert response.status_code == 200, response.text
    return [n for n in response.json()["notificacoes"] if n["tipo"] == tipo]


def setor_do_sku(client: TestClient, sku: SKU) -> str | None:
    response = client.get(f"/skus/{sku.sku_code}/setor")
    assert response.status_code == 200, response.text
    setor = response.json()["setor"]
    return setor and setor["nome"]


def test_o_aviso_grava_quem_avisou_o_setor_e_o_disponivel_do_momento(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)

    criado = avisar_gondola(client, TAPETE_CINZA, comentario="  Só sobrou o P.  ")

    assert criado["sku_code"] == TAPETE_CINZA.sku_code
    assert criado["setor_id"] == str(TAPETES.id)
    assert criado["comentario"] == "Só sobrou o P."
    assert criado["avisado_por"] == "Bia"
    assert criado["disponivel_no_erp"] == 500
    assert criado["criado_em"] == iso(AGORA)


def test_o_aviso_poe_o_sku_no_topo_do_painel_do_repositor(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA, comentario="Cliente procurou e não achou.")

    como(cenario, RAFA)
    resultado = do_repositor(client)

    [aviso] = resultado["avisos_de_gondola"]
    assert aviso["sku_code"] == TAPETE_CINZA.sku_code
    assert (aviso["produto_nome"], aviso["cor"], aviso["tamanho"]) == ("Tapete Banheiro", "cinza", "40x60")
    assert aviso["disponivel"] == 500
    assert aviso["setor"] == {"id": str(TAPETES.id), "nome": "Tapetes", "ativo": True}
    assert [(a["avisado_por"], a["comentario"]) for a in aviso["avisos"]] == [("Bia", "Cliente procurou e não achou.")]
    assert aviso["queda"] is None
    assert codigos(resultado["quedas_de_venda"]) == [TAPETE.sku_code]


def test_os_avisos_vem_do_mais_antigo_para_o_mais_recente_e_juntam_o_mesmo_sku(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, RARO, MESA)
    cenario.relogio.avancar(minutes=10)
    avisar_gondola(client, TAPETE_CINZA)
    cenario.relogio.avancar(minutes=10)
    como(cenario, ANA)
    avisar_gondola(client, RARO, MESA, comentario="Ainda vazia.")
    como(cenario, RAFA)

    resultado = do_repositor(client)

    assert codigos(resultado["avisos_de_gondola"]) == [RARO.sku_code, TAPETE_CINZA.sku_code]
    assert [a["avisado_por"] for a in resultado["avisos_de_gondola"][0]["avisos"]] == ["Bia", "Ana"]


def test_sku_com_aviso_e_queda_de_venda_aparece_uma_vez_com_os_dois(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE)
    como(cenario, RAFA)

    resultado = do_repositor(client)

    [aviso] = resultado["avisos_de_gondola"]
    assert aviso["sku_code"] == TAPETE.sku_code
    assert aviso["queda"]["vendido_na_janela"] == 5
    assert aviso["queda"]["venda_perdida"] == pytest.approx(15)
    assert resultado["quedas_de_venda"] == []


def test_a_vendedora_avisa_mesmo_com_o_erp_zerado(client: TestClient) -> None:
    cenario = preparar({TAPETE_CINZA.sku_code: 0})
    como(cenario, BIA)

    criado = avisar_gondola(client, TAPETE_CINZA)

    assert criado["disponivel_no_erp"] == 0
    como(cenario, RAFA)
    [aviso] = do_repositor(client)["avisos_de_gondola"]
    assert aviso["disponivel"] == 0


def test_o_aviso_notifica_na_hora_o_papel_reposicao(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA, comentario="Cliente procurou.")

    como(cenario, RAFA)
    [notificacao] = notificacoes(client, "gondola_vazia")

    assert notificacao["sku_code"] == TAPETE_CINZA.sku_code
    assert notificacao["lida"] is False
    assert notificacao["aberto_em"] == iso(AGORA)
    assert notificacao["detalhe"] == {
        "produto_nome": "Tapete Banheiro",
        "cor": "cinza",
        "tamanho": "40x60",
        "setor": "Tapetes",
        "avisado_por": "Bia",
        "comentario": "Cliente procurou.",
        "disponivel_no_erp": 500,
    }
    como(cenario, CARLA)
    assert notificacoes(client, "gondola_vazia") == []
    como(cenario, ANA)
    assert notificacoes(client, "gondola_vazia") == []


def test_a_verificacao_fecha_o_aviso(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA)
    cenario.relogio.avancar(minutes=20)

    como(cenario, RAFA)
    verificar(client, TAPETE_CINZA, "repus")

    resultado = do_repositor(client)
    assert resultado["avisos_de_gondola"] == []
    assert TAPETE_CINZA.sku_code not in codigos(resultado["quedas_de_venda"])


def test_a_verificacao_de_antes_do_aviso_nao_fecha(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, RAFA)
    verificar(client, TAPETE_CINZA, "repus")
    cenario.relogio.avancar(minutes=20)
    como(cenario, BIA)

    avisar_gondola(client, TAPETE_CINZA)

    como(cenario, RAFA)
    assert codigos(do_repositor(client)["avisos_de_gondola"]) == [TAPETE_CINZA.sku_code]


def test_a_verificacao_notifica_cada_vendedora_que_avisou_uma_vez(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA)
    avisar_gondola(client, TAPETE_CINZA, comentario="De novo.")
    como(cenario, ANA)
    avisar_gondola(client, TAPETE_CINZA)
    cenario.relogio.avancar(minutes=20)
    como(cenario, RAFA)
    verificar(client, TAPETE_CINZA, "estava_na_gondola", comentario="Estava no corredor errado.")
    cenario.relogio.avancar(minutes=20)
    verificar(client, TAPETE_CINZA, "repus")

    como(cenario, BIA)
    [notificacao] = notificacoes(client, "verificacao_sobre_aviso")
    assert notificacao["sku_code"] == TAPETE_CINZA.sku_code
    assert notificacao["aberto_em"] == iso(AGORA + timedelta(minutes=20))
    assert notificacao["detalhe"] == {
        "produto_nome": "Tapete Banheiro",
        "cor": "cinza",
        "tamanho": "40x60",
        "resultado": "estava_na_gondola",
        "comentario": "Estava no corredor errado.",
        "verificado_por": "Rafa",
    }
    como(cenario, ANA)
    assert len(notificacoes(client, "verificacao_sobre_aviso")) == 1
    como(cenario, RAFA)
    assert notificacoes(client, "verificacao_sobre_aviso") == []


def test_verificacao_sem_aviso_aberto_nao_notifica_ninguem(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, RAFA)
    verificar(client, TAPETE, "repus")

    como(cenario, BIA)
    assert notificacoes(client, "verificacao_sobre_aviso") == []


def test_o_setor_do_aviso_vira_o_setor_conhecido_do_sku(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    assert setor_do_sku(client, TAPETE_CINZA) is None

    avisar_gondola(client, TAPETE_CINZA, MESA)

    assert setor_do_sku(client, TAPETE_CINZA) == "Mesa"


def test_a_verificacao_corrige_o_setor_e_o_proximo_aviso_ja_vem_certo(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA, MESA)
    cenario.relogio.avancar(minutes=20)
    como(cenario, RAFA)

    verificar(client, TAPETE_CINZA, "repus", setor_id=str(TAPETES.id))

    assert setor_do_sku(client, TAPETE_CINZA) == "Tapetes"


def test_a_queda_de_venda_mostra_o_setor_conhecido_quando_ha(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, RAFA)
    assert do_repositor(client)["quedas_de_venda"][0]["setor"] is None

    conhecer_o_setor(cenario, TAPETE, TAPETES)

    assert do_repositor(client)["quedas_de_venda"][0]["setor"]["nome"] == "Tapetes"


def test_o_filtro_por_setor_vale_para_os_dois_grupos(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, RARO, MESA)
    avisar_gondola(client, TAPETE_CINZA, TAPETES)
    conhecer_o_setor(cenario, TAPETE, TAPETES)
    como(cenario, RAFA)

    de_tapetes = do_repositor(client, setor=str(TAPETES.id))
    de_mesa = do_repositor(client, setor=str(MESA.id))

    assert codigos(de_tapetes["avisos_de_gondola"]) == [TAPETE_CINZA.sku_code]
    assert codigos(de_tapetes["quedas_de_venda"]) == [TAPETE.sku_code]
    assert codigos(de_mesa["avisos_de_gondola"]) == [RARO.sku_code]
    assert de_mesa["quedas_de_venda"] == []


def test_sem_estoque_no_deposito_num_aviso_com_o_erp_dizendo_que_tem_e_estoque_divergente(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA)
    cenario.relogio.avancar(minutes=20)
    como(cenario, RAFA)

    verificar(client, TAPETE_CINZA, "sem_estoque_no_deposito")

    como(cenario, CARLA)
    item = next(i for i in painel(client)["alertas"] if i["sku_code"] == TAPETE_CINZA.sku_code)
    assert item["grupo"] == "estoque_divergente"


def test_sem_estoque_no_deposito_num_aviso_com_o_erp_zerado_nao_e_estoque_divergente(client: TestClient) -> None:
    cenario = preparar({TAPETE_CINZA.sku_code: 0})
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA)
    cenario.relogio.avancar(minutes=20)
    como(cenario, RAFA)

    verificar(client, TAPETE_CINZA, "sem_estoque_no_deposito")

    como(cenario, CARLA)
    item = next((i for i in painel(client)["alertas"] if i["sku_code"] == TAPETE_CINZA.sku_code), None)
    assert item is None or "estoque_divergente" not in item["motivos"]


def test_meus_avisos_junta_os_avisos_ao_comprador_e_ao_repositor(client: TestClient) -> None:
    cenario = preparar({ZERADO.sku_code: 0})
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA, comentario="Só sobrou o P.")
    cenario.relogio.avancar(minutes=10)
    avisar(client, ZERADO, "acabou")
    cenario.relogio.avancar(minutes=10)
    avisar_gondola(client, RARO, MESA)
    cenario.relogio.avancar(minutes=10)
    como(cenario, RAFA)
    verificar(client, TAPETE_CINZA, "sem_estoque_no_deposito", comentario="Nem no depósito.")
    como(cenario, CARLA)
    decidir(client, ZERADO, "negociando")

    como(cenario, BIA)
    raro, zerado, cinza = meus_avisos(client)

    assert (raro["para"], raro["tipo"], raro["setor"], raro["verificacao"]) == ("repositor", "gondola_vazia", "Mesa", None)
    assert (zerado["para"], zerado["tipo"], zerado["decisao"]["tipo"]) == ("comprador", "acabou", "negociando")
    assert zerado["verificacao"] is None
    assert (cinza["sku_code"], cinza["produto_nome"], cinza["cor"]) == (TAPETE_CINZA.sku_code, "Tapete Banheiro", "cinza")
    assert (cinza["setor"], cinza["comentario"], cinza["decisao"]) == ("Tapetes", "Só sobrou o P.", None)
    assert cinza["verificacao"] == {
        "resultado": "sem_estoque_no_deposito",
        "comentario": "Nem no depósito.",
        "criado_em": iso(AGORA + timedelta(minutes=30)),
    }
    como(cenario, ANA)
    assert meus_avisos(client) == []


def test_avisos_de_gondola_de_mais_de_30_dias_saem_de_meus_avisos(client: TestClient) -> None:
    cenario = preparar()
    como(cenario, BIA)
    avisar_gondola(client, TAPETE_CINZA)

    cenario.relogio.avancar(days=31)

    assert meus_avisos(client) == []


def test_sku_desconhecido_responde_404_e_inativo_422(client: TestClient) -> None:
    cenario = preparar()
    cenario.erp.skus.append(make_sku("PM-VERM-140-01", ativo=False))
    cenario.erp.estoques_por_sku["PM-VERM-140-01"] = make_estoque(disponivel=3)

    novo = {"setor_id": str(TAPETES.id)}
    assert client.post("/avisos-gondola", json={"sku_code": "NAO-EXISTE", **novo}).status_code == 404
    assert client.post("/avisos-gondola", json={"sku_code": "PM-VERM-140-01", **novo}).status_code == 422


def test_setor_inativo_ou_desconhecido_responde_422(client: TestClient) -> None:
    preparar()

    for setor_id in (COZINHA.id, uuid4()):
        aviso = {"sku_code": TAPETE_CINZA.sku_code, "setor_id": str(setor_id)}
        verificacao = {"resultado": "repus", "setor_id": str(setor_id)}
        assert client.post("/avisos-gondola", json=aviso).status_code == 422
        assert client.post(f"/skus/{TAPETE_CINZA.sku_code}/verificacoes", json=verificacao).status_code == 422
    assert client.get("/reposicao/painel").json()["avisos_de_gondola"] == []


@pytest.mark.parametrize("papel", ["comprador", "reposicao", "admin"])
def test_so_a_vendedora_avisa_a_gondola_vazia(client: TestClient, papel: Papel) -> None:
    preparar()
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    response = client.post("/avisos-gondola", json={"sku_code": TAPETE_CINZA.sku_code, "setor_id": str(TAPETES.id)})

    assert response.status_code == 403
