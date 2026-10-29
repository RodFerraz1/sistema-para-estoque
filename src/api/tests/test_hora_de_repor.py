"""Testes HTTP da hora de repor (`hora_de_repor` em `/reposicao/painel`), da montagem da
gôndola (`/reposicao/produtos/{id}/montagem`) e do dashboard do repositor
(`/reposicao/dashboard`).

Mesmo cenário do `test_mix_de_gondola.py`: o relógio fica na segunda-feira às 9h e as 5 cores
do Tapete Banheiro venderam todo dia aberto, às 15h, marrom 10, cinza 5, azul 3, bege 2 e
branco 1. Com 21 lugares, o mix põe 9 marrons, 5 cinzas, 3 azuis, 2 beges e 2 brancos: cada
cor segura mais ou menos um dia de venda. A montagem fica no sábado às 8h, antes das vendas
do sábado. O Rafa repõe; a Bia é vendedora.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import BOA_VISTA, DEPENDENCIAS, Cenario, decidir, preparar
from src.api.tests.test_meus_avisos import como
from src.api.tests.test_mix_de_gondola import (
    AZUL,
    BEGE,
    BRANCO,
    CINZA,
    LOJA,
    MARROM,
    PANO_AMARELO,
    PANO_PRETO,
    POR_DIA,
    RAFA,
    TAPETES,
    vendeu_todo_dia,
)
from src.api.tests.test_reposicao import AGORA, REGULAR, dias_abertos, vendas
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.reposicao.schemas import Setor, SetorDoSku
from src.usuarios.dependencies import usuario_atual
from tests.fakes import make_estoque, make_fornecedor_sku, make_usuario

BIA = make_usuario("Bia", papeis=["vendas"])
CARLA = make_usuario("Carla", papeis=["comprador"])
SETOR = Setor(id=uuid4(), nome="Tapetes", ativo=True)
SABADO_8H = datetime.combine(dias_abertos(1)[0], time(8), tzinfo=UTC)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in (*DEPENDENCIAS, usuario_atual):
        app.dependency_overrides.pop(dependencia, None)


def preparar_tapetes(disponiveis: dict[str, int] | None = None, *outras_vendas: list, **parametros: object) -> Cenario:
    skus = [*TAPETES, PANO_PRETO, PANO_AMARELO, REGULAR, LOJA]
    disponiveis = disponiveis or {}
    lojas = [v for sku, q in POR_DIA for v in vendeu_todo_dia(sku, q, 40)] if not outras_vendas else []
    erp = InMemoryERPAdapter(
        skus=skus,
        fornecedores=[BOA_VISTA],
        fornecedores_por_sku={s.sku_code: [make_fornecedor_sku(BOA_VISTA)] for s in skus},
        estoques={s.sku_code: make_estoque(disponivel=disponiveis.get(s.sku_code, 400)) for s in skus},
        vendas=[*lojas, *(v for lista in outras_vendas for v in lista), *vendeu_todo_dia(LOJA, 6, 40)],
    )
    cenario = preparar(erp=erp, **{"dias_mix_gondola": 30, **parametros})
    cenario.setores.gravar(SETOR)
    como(cenario, RAFA)
    return cenario


def montar(client: TestClient, cenario: Cenario, capacidade: int = 21, quando: datetime = SABADO_8H) -> list[dict]:
    cenario.relogio.agora = quando
    response = client.post(f"/reposicao/produtos/{MARROM.produto_id}/montagem", json={"capacidade": capacidade})
    cenario.relogio.agora = AGORA
    assert response.status_code == 201, response.text
    return response.json()


def hora_de_repor(client: TestClient) -> list[dict]:
    response = client.get("/reposicao/painel")
    assert response.status_code == 200, response.text
    return response.json()["hora_de_repor"]


def cores(itens: list[dict]) -> list[str]:
    return [i["cor"] for i in itens]


def test_o_que_vendeu_desde_a_montagem_esvaziou_a_gondola_e_e_hora_de_repor(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)

    itens = hora_de_repor(client)

    assert cores(itens) == ["marrom", "cinza", "azul", "bege"]
    marrom = itens[0]
    assert (marrom["sku_code"], marrom["produto_id"], marrom["disponivel"]) == (MARROM.sku_code, str(MARROM.produto_id), 400)
    assert marrom["reposicao"] == {
        "pecas_no_mix": 9,
        "na_gondola": 0,
        "a_repor": 9,
        "venda_media_diaria": pytest.approx(10),
        "dias_na_gondola": 0,
        "vendido_desde": 10,
        "reposto_em": SABADO_8H.isoformat().replace("+00:00", "Z"),
        "reposto_por": "Rafa",
    }


def test_quem_ainda_segura_mais_de_meio_dia_de_venda_fica_de_fora(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)

    assert BRANCO.sku_code not in {i["sku_code"] for i in hora_de_repor(client)}


def test_repus_depois_das_vendas_tira_a_cor_da_hora_de_repor(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)

    response = client.post(f"/skus/{MARROM.sku_code}/verificacoes", json={"resultado": "repus"})

    assert response.status_code == 201, response.text
    assert cores(hora_de_repor(client)) == ["cinza", "azul", "bege"]


def test_estava_na_gondola_nao_conta_como_reposicao(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)

    client.post(f"/skus/{MARROM.sku_code}/verificacoes", json={"resultado": "estava_na_gondola"})

    assert cores(hora_de_repor(client))[0] == "marrom"


def test_sem_reposicao_registrada_nao_ha_de_onde_descontar(client: TestClient) -> None:
    preparar_tapetes()

    response = client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": 21})

    assert response.status_code == 200, response.text
    assert hora_de_repor(client) == []


def test_a_politica_decide_com_quantos_dias_de_venda_na_gondola_repor(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario, capacidade=42)
    assert hora_de_repor(client) == []

    cenario = preparar_tapetes(piso_gondola_dias=1.0)
    montar(client, cenario, capacidade=42)

    itens = hora_de_repor(client)
    assert cores(itens) == ["marrom", "cinza", "azul", "bege"]
    assert [i["reposicao"]["na_gondola"] for i in itens] == [9, 5, 3, 2]
    assert [i["reposicao"]["a_repor"] for i in itens] == [10, 5, 3, 2]
    assert itens[0]["reposicao"]["dias_na_gondola"] == pytest.approx(0.9)


def test_sem_estoque_alem_do_que_esta_na_gondola_nao_ha_o_que_repor(client: TestClient) -> None:
    cenario = preparar_tapetes({BRANCO.sku_code: 2}, piso_gondola_dias=10)
    montar(client, cenario, quando=AGORA)

    assert cores(hora_de_repor(client)) == ["marrom", "cinza", "azul", "bege"]


def test_gondola_vazia_avisada_fica_so_no_aviso(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)
    como(cenario, BIA)

    response = client.post("/avisos-gondola", json={"sku_code": CINZA.sku_code, "setor_id": str(SETOR.id)})
    como(cenario, RAFA)

    assert response.status_code == 201, response.text
    painel = client.get("/reposicao/painel").json()
    assert [a["sku_code"] for a in painel["avisos_de_gondola"]] == [CINZA.sku_code]
    assert cores(painel["hora_de_repor"]) == ["marrom", "azul", "bege"]


def test_a_hora_de_repor_segue_os_filtros_e_mostra_o_setor(client: TestClient) -> None:
    cenario = preparar_tapetes()
    montar(client, cenario)
    cenario.setores.lembrar(SetorDoSku(sku_code=MARROM.sku_code, setor_id=SETOR.id, atualizado_em=AGORA, usuario_id=None))

    [marrom] = client.get("/reposicao/painel", params={"setor": str(SETOR.id)}).json()["hora_de_repor"]

    assert (marrom["sku_code"], marrom["setor"]["nome"]) == (MARROM.sku_code, "Tapetes")
    assert cores(client.get("/reposicao/painel", params={"busca": "bege"}).json()["hora_de_repor"]) == ["bege"]


def test_montar_a_gondola_grava_a_capacidade_e_repus_em_cada_cor_que_ganhou_peca(client: TestClient) -> None:
    cenario = preparar_tapetes({BRANCO.sku_code: 0})

    verificacoes = montar(client, cenario, quando=AGORA)

    assert {v["sku_code"] for v in verificacoes} == {MARROM.sku_code, CINZA.sku_code, AZUL.sku_code, BEGE.sku_code}
    assert {(v["resultado"], v["verificado_por"]) for v in verificacoes} == {("repus", "Rafa")}
    [tapete] = [p for p in client.get("/reposicao/produtos").json() if p["produto_id"] == str(MARROM.produto_id)]
    assert tapete["capacidade"] == 21


def test_montar_a_gondola_fecha_o_aviso_de_gondola_vazia(client: TestClient) -> None:
    cenario = preparar_tapetes()
    como(cenario, BIA)
    client.post("/avisos-gondola", json={"sku_code": CINZA.sku_code, "setor_id": str(SETOR.id)})
    como(cenario, RAFA)
    cenario.relogio.avancar(minutes=5)

    montar(client, cenario, quando=cenario.relogio.agora)

    assert client.get("/reposicao/painel").json()["avisos_de_gondola"] == []


@pytest.mark.parametrize(
    ("produto_id", "capacidade", "status"),
    [(uuid4(), 10, 404), (MARROM.produto_id, 0, 422)],
)
def test_montagem_recusa_produto_desconhecido_e_capacidade_sem_lugar(
    client: TestClient, produto_id: object, capacidade: int, status: int
) -> None:
    preparar_tapetes()

    response = client.post(f"/reposicao/produtos/{produto_id}/montagem", json={"capacidade": capacidade})

    assert response.status_code == status


def preparar_dashboard() -> Cenario:
    """O marrom vendia 10 por dia e vendeu 5 e 0 na sexta e no sábado; o cinza vende 5 por
    dia e foi reposto no sábado às 8h; a toalha bege vende normalmente."""
    cenario = preparar_tapetes(
        None,
        vendas(MARROM, 10, 5, 0),
        vendeu_todo_dia(CINZA, 5, 40),
        vendas(REGULAR, 4, 4, 4),
    )
    client = TestClient(app)
    assert client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": 6}).status_code == 200
    cenario.relogio.agora = SABADO_8H
    assert client.post(f"/skus/{CINZA.sku_code}/verificacoes", json={"resultado": "repus"}).status_code == 201
    cenario.relogio.agora = AGORA
    return cenario


def avisar(client: TestClient, cenario: Cenario, sku: SKU, **campos: object) -> None:
    como(cenario, BIA)
    response = client.post("/avisos-gondola", json={"sku_code": sku.sku_code, "setor_id": str(SETOR.id), **campos})
    assert response.status_code == 201, response.text
    como(cenario, RAFA)
    cenario.relogio.avancar(minutes=1)


def dashboard(client: TestClient) -> list[dict]:
    response = client.get("/reposicao/dashboard")
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_poe_quem_parou_de_vender_antes_dos_avisos_e_da_hora_de_repor(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, REGULAR)

    gondolas = dashboard(client)

    assert [(g["prioridade"], g["sku_code"]) for g in gondolas] == [
        ("parou_de_vender", MARROM.sku_code),
        ("gondola_vazia", REGULAR.sku_code),
        ("hora_de_repor", CINZA.sku_code),
    ]
    marrom, toalha, cinza = gondolas
    assert (marrom["queda"]["venda_perdida"], marrom["avisos"], marrom["reposicao"]) == (pytest.approx(15), [], None)
    assert [a["avisado_por"] for a in toalha["avisos"]] == ["Bia"]
    assert (toalha["queda"], toalha["setor"]["nome"]) == (None, "Tapetes")
    assert (cinza["reposicao"]["na_gondola"], cinza["reposicao"]["vendido_desde"]) == (0, 5)


def test_dashboard_diz_quantas_pecas_levar_e_sem_capacidade_nao_sabe(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, REGULAR)

    marrom, toalha, cinza = dashboard(client)

    assert marrom["a_repor"] == 2
    assert toalha["a_repor"] is None
    assert cinza["a_repor"] == cinza["reposicao"]["a_repor"] == 1


def test_quem_parou_de_vender_e_tambem_foi_avisado_aparece_uma_vez_com_mais_de_um_motivo(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, REGULAR)
    avisar(client, cenario, MARROM)

    gondolas = dashboard(client)

    assert [(g["prioridade"], g["sku_code"]) for g in gondolas] == [
        ("mais_de_um_motivo", MARROM.sku_code),
        ("gondola_vazia", REGULAR.sku_code),
        ("hora_de_repor", CINZA.sku_code),
    ]
    marrom = gondolas[0]
    assert (marrom["queda"]["venda_perdida"], [a["avisado_por"] for a in marrom["avisos"]]) == (pytest.approx(15), ["Bia"])
    assert marrom["a_repor"] == 2


def test_aviso_na_hora_de_repor_fica_acima_de_quem_so_parou_de_vender(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, CINZA)

    cinza, marrom = dashboard(client)

    assert (cinza["prioridade"], cinza["sku_code"]) == ("mais_de_um_motivo", CINZA.sku_code)
    assert [a["avisado_por"] for a in cinza["avisos"]] == ["Bia"]
    assert (cinza["reposicao"]["vendido_desde"], cinza["a_repor"]) == (5, 1)
    assert (marrom["prioridade"], marrom["sku_code"]) == ("parou_de_vender", MARROM.sku_code)
    assert [a["sku_code"] for a in client.get("/reposicao/painel").json()["avisos_de_gondola"]] == [CINZA.sku_code]
    assert hora_de_repor(client) == []


def test_dashboard_sem_nada_a_repor_vem_vazio(client: TestClient) -> None:
    preparar_tapetes()

    assert dashboard(client) == []


def sugestao(client: TestClient, sku: SKU) -> dict:
    response = client.get(f"/skus/{sku.sku_code}/sugestao-gondola")
    assert response.status_code == 200, response.text
    return response.json()


def test_a_vendedora_ve_as_pecas_do_mix_e_sem_capacidade_nao_ha_sugestao(client: TestClient) -> None:
    cenario = preparar_dashboard()
    como(cenario, BIA)

    assert sugestao(client, MARROM) == {"pecas": 2, "capacidade": 6, "disponivel": 400}
    assert sugestao(client, REGULAR) == {"pecas": None, "capacidade": None, "disponivel": 400}
    assert client.get("/skus/NAO-EXISTE/sugestao-gondola").status_code == 404


def test_as_pecas_que_a_vendedora_pede_valem_no_lugar_do_mix(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, REGULAR, pecas=8)
    avisar(client, cenario, MARROM, pecas=5)
    avisar(client, cenario, MARROM)

    gondolas = {g["sku_code"]: g for g in dashboard(client)}

    assert gondolas[REGULAR.sku_code]["a_repor"] == 8
    assert gondolas[MARROM.sku_code]["a_repor"] == 5
    assert [a["pecas"] for a in gondolas[MARROM.sku_code]["avisos"]] == [5, None]
    painel = client.get("/reposicao/painel").json()["avisos_de_gondola"]
    assert {a["sku_code"]: [x["pecas"] for x in a["avisos"]] for a in painel} == {
        MARROM.sku_code: [5, None],
        REGULAR.sku_code: [8],
    }
    como(cenario, BIA)
    assert [a["pecas"] for a in client.get("/avisos/meus").json()] == [None, 5, 8]


@pytest.mark.parametrize("pecas", [0, -1, 10_001])
def test_aviso_recusa_pecas_fora_do_razoavel(client: TestClient, pecas: int) -> None:
    cenario = preparar_dashboard()
    como(cenario, BIA)

    response = client.post("/avisos-gondola", json={"sku_code": MARROM.sku_code, "setor_id": str(SETOR.id), "pecas": pecas})

    assert response.status_code == 422


def faltou(client: TestClient, sku: SKU, pedidas: int, repostas: int, **campos: object):
    return client.post(
        f"/skus/{sku.sku_code}/falta-na-gondola",
        json={"pecas_pedidas": pedidas, "pecas_repostas": repostas, **campos},
    )


def test_o_repositor_repoe_o_que_tem_e_pede_ao_comprador_o_que_faltou(client: TestClient) -> None:
    cenario = preparar_dashboard()
    avisar(client, cenario, MARROM, pecas=50)

    response = faltou(client, MARROM, 50, 35, comentario="Só tinha uma caixa.")

    assert response.status_code == 201, response.text
    aviso = response.json()
    assert (aviso["tipo"], aviso["quantidade"], aviso["avisado_por"]) == ("faltou_na_gondola", 15, "Rafa")
    assert aviso["comentario"] == "Só tinha uma caixa."
    assert client.get("/reposicao/painel").json()["avisos_de_gondola"] == []
    como(cenario, BIA)
    [meu] = client.get("/avisos/meus").json()
    assert meu["verificacao"]["resultado"] == "repus"
    assert meu["verificacao"]["comentario"] == (
        "Repus 35 de 50 peças; pedi as 15 que faltaram ao comprador. Só tinha uma caixa."
    )
    como(cenario, CARLA)
    [item] = [a for a in client.get("/painel").json()["alertas"] if a["sku_code"] == MARROM.sku_code]
    assert (item["ultimo_aviso"]["tipo"], item["ultimo_aviso"]["quantidade"]) == ("faltou_na_gondola", 15)
    [notificacao] = [n for n in client.get("/notificacoes").json()["notificacoes"] if n["tipo"] == "aviso"]
    assert (notificacao["detalhe"]["tipo"], notificacao["detalhe"]["quantidade"]) == ("faltou_na_gondola", 15)


def test_a_decisao_do_comprador_avisa_o_repositor_que_pediu(client: TestClient) -> None:
    cenario = preparar_dashboard()
    assert faltou(client, MARROM, 50, 35).status_code == 201
    como(cenario, CARLA)

    decidir(client, MARROM, "vou_comprar", quantidade=120)

    como(cenario, RAFA)
    [decisao] = [n for n in client.get("/notificacoes").json()["notificacoes"] if n["tipo"] == "decisao_sobre_aviso"]
    assert (decisao["detalhe"]["tipo"], decisao["detalhe"]["quantidade"]) == ("vou_comprar", 120)


@pytest.mark.parametrize(("pedidas", "repostas"), [(50, 50), (50, 60), (10, 0), (1, 1)])
def test_sem_falta_nao_ha_o_que_pedir_ao_comprador(client: TestClient, pedidas: int, repostas: int) -> None:
    preparar_dashboard()

    assert faltou(client, MARROM, pedidas, repostas).status_code == 422


def test_a_vendedora_nao_registra_falta_na_gondola(client: TestClient) -> None:
    cenario = preparar_dashboard()
    como(cenario, BIA)

    assert faltou(client, MARROM, 50, 35).status_code == 403
    response = client.post("/avisos", json={"sku_code": MARROM.sku_code, "tipo": "faltou_na_gondola"})
    assert response.status_code == 422
