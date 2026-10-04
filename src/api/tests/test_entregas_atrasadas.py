"""Testes HTTP das entregas atrasadas no painel, da cobrança de entrega
(`/pedidos/{id}/cobrancas`), do histórico de atrasos do fornecedor e das entregas pendentes
do SKU, com relógio injetado. Cenário em `cenario_painel.py`: hoje é 01/10/2026."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    BOA_VISTA,
    KATRINA,
    REGULAR,
    SOBRANDO,
    URGENTE,
    ZERADO,
    atrasar,
    avisar,
    client,  # noqa: F401 (fixture)
    codigos,
    painel,
    preparar,
)
from src.erp_adapter.in_memory import PedidoCompra
from src.erp_adapter.schemas import StatusPedidoCompra
from src.politica_compra.schemas import MotivoAlerta
from src.usuarios.schemas import Usuario
from tests.fakes import make_pedido_compra

HOJE = date(2026, 10, 1)


def entregas(client: TestClient, **filtros: str) -> list[dict]:
    response = client.get("/painel", params=filtros)
    assert response.status_code == 200, response.text
    return response.json()["entregas_atrasadas"]


def pedidos(client: TestClient) -> list[str]:
    return [p["pedido_id"] for f in entregas(client) for p in f["pedidos"]]


def cobrar(client: TestClient, pedido: PedidoCompra, **corpo: str) -> dict:
    response = client.post(f"/pedidos/{pedido.id}/cobrancas", json=corpo)
    assert response.status_code == 201, response.text
    return response.json()


def test_entrega_prevista_para_ontem_entra_agrupada_por_fornecedor(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))

    resultado = painel(client)

    assert resultado["entregas_atrasadas"] == [
        {
            "fornecedor_id": str(BOA_VISTA.id),
            "fornecedor_nome": "Boa Vista Têxtil",
            "tem_sku_em_ruptura": False,
            "maior_atraso_dias": 1,
            "pedidos": [
                {
                    "pedido_id": str(pedido.id),
                    "status": "enviado",
                    "data_prevista_entrega": "2026-09-30",
                    "dias_de_atraso": 1,
                    "ultima_cobranca": None,
                    "skus": [
                        {
                            "sku_code": REGULAR.sku_code,
                            "produto_nome": "Toalha Banho Conforto",
                            "cor": "bege",
                            "tamanho": "70x140",
                            "quantidade_pendente": 120,
                            "disponivel": 150,
                            "cobertura_dias": pytest.approx(45.0),
                            "em_ruptura": False,
                        }
                    ],
                }
            ],
        }
    ]
    [item] = [i for i in resultado["alertas"] if i["sku_code"] == REGULAR.sku_code]
    assert (item["motivos"], item["grupo"]) == (["entrega_atrasada"], "entregas_atrasadas")
    assert resultado["contagens"]["entregas_atrasadas"] == 1


def test_entrega_prevista_para_hoje_nao_entra(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), prevista=HOJE)

    resultado = painel(client)

    assert resultado["entregas_atrasadas"] == []
    assert REGULAR.sku_code not in codigos(resultado["alertas"])


def test_pedido_sem_data_prevista_nunca_esta_atrasado(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), prevista=None)
    cenario.relogio.avancar(days=365)

    assert entregas(client) == []


@pytest.mark.parametrize("status", ["recebido_total", "rascunho", "cancelado"])
def test_pedido_fechado_nunca_esta_atrasado(client: TestClient, status: StatusPedidoCompra) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), status=status, prevista=date(2026, 8, 1))

    assert entregas(client) == []


@pytest.mark.parametrize("status", ["aprovado", "enviado", "recebido_parcial"])
def test_pedido_aberto_com_pendente_esta_atrasado(client: TestClient, status: StatusPedidoCompra) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), status=status, recebida=50, prevista=date(2026, 9, 21))

    [fornecedor] = entregas(client)

    [pedido] = fornecedor["pedidos"]
    assert (pedido["status"], pedido["dias_de_atraso"]) == (status, 10)
    assert pedido["skus"][0]["quantidade_pendente"] == 70


def test_sku_em_ruptura_com_entrega_atrasada_vai_para_as_entregas_e_nao_para_a_ruptura(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (URGENTE, 100))

    resultado = painel(client)

    [item] = [i for i in resultado["alertas"] if i["sku_code"] == URGENTE.sku_code]
    assert item["grupo"] == "entregas_atrasadas"
    assert set(item["motivos"]) == {"abaixo_do_piso_alerta", "entrega_atrasada"}
    [fornecedor] = resultado["entregas_atrasadas"]
    assert fornecedor["tem_sku_em_ruptura"] is True
    assert fornecedor["pedidos"][0]["skus"][0]["em_ruptura"] is True


def test_fornecedor_com_sku_em_ruptura_vem_primeiro(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), prevista=date(2026, 9, 21), key="boa-vista")
    atrasar(cenario, KATRINA, (ZERADO, 50), key="katrina")

    nomes = [f["fornecedor_nome"] for f in entregas(client)]

    assert nomes == ["Katrina Têxtil", "Boa Vista Têxtil"]


def test_sem_ruptura_vem_primeiro_o_fornecedor_com_o_maior_atraso(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), key="boa-vista")
    atrasar(cenario, KATRINA, (SOBRANDO, 50), prevista=date(2026, 9, 26), key="katrina-recente")
    antigo = atrasar(cenario, KATRINA, (SOBRANDO, 30), prevista=date(2026, 9, 1), key="katrina-antigo")

    resultado = entregas(client)

    assert [(f["fornecedor_nome"], f["maior_atraso_dias"]) for f in resultado] == [
        ("Katrina Têxtil", 30),
        ("Boa Vista Têxtil", 1),
    ]
    assert [p["dias_de_atraso"] for p in resultado[0]["pedidos"]] == [30, 5]
    assert resultado[0]["pedidos"][0]["pedido_id"] == str(antigo.id)


def test_cobranca_tira_o_pedido_do_painel_ate_a_nova_previsao(client: TestClient, usuario_logado: Usuario) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))

    cobranca = cobrar(client, pedido, nova_previsao="2026-10-05", comentario=" Caminhão parado na estrada. ")

    assert cobranca == {
        "id": cobranca["id"],
        "pedido_id": str(pedido.id),
        "fornecedor_id": str(BOA_VISTA.id),
        "nova_previsao": "2026-10-05",
        "comentario": "Caminhão parado na estrada.",
        "cobrado_por": usuario_logado.nome,
        "criado_em": "2026-10-01T09:00:00Z",
    }
    assert [c.usuario_id for c in cenario.cobrancas.listar(pedido.id)] == [usuario_logado.id]
    resultado = painel(client)
    assert resultado["entregas_atrasadas"] == []
    assert REGULAR.sku_code not in codigos(resultado["alertas"])
    cenario.relogio.agora = datetime(2026, 10, 5, 23, 0, tzinfo=UTC)
    assert entregas(client) == []


def test_nova_previsao_vencida_traz_o_pedido_de_volta(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))
    cobranca = cobrar(client, pedido, nova_previsao="2026-10-05")
    cenario.relogio.agora = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)

    [fornecedor] = entregas(client)

    [voltou] = fornecedor["pedidos"]
    assert voltou["dias_de_atraso"] == 6
    assert voltou["ultima_cobranca"] == cobranca


def test_cobranca_sem_nova_previsao_vale_7_dias(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))
    cobrar(client, pedido, comentario="Disse que manda essa semana.")

    cenario.relogio.avancar(days=6, hours=23)
    assert entregas(client) == []
    cenario.relogio.avancar(hours=1)
    assert pedidos(client) == [str(pedido.id)]


def test_cobranca_vale_para_o_pedido_inteiro_e_so_para_ele(client: TestClient) -> None:
    cenario = preparar()
    cobrado = atrasar(cenario, BOA_VISTA, (REGULAR, 120), (SOBRANDO, 40), key="cobrado")
    outro = atrasar(cenario, BOA_VISTA, (SOBRANDO, 10), key="outro")

    cobrar(client, cobrado)

    assert pedidos(client) == [str(outro.id)]
    assert codigos(painel(client)["alertas"]).count(REGULAR.sku_code) == 0


def test_vale_a_cobranca_mais_recente_do_pedido(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))
    cobrar(client, pedido, nova_previsao="2026-10-10")
    cenario.relogio.avancar(days=1)
    cobrar(client, pedido, nova_previsao="2026-10-03")

    cenario.relogio.agora = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)

    assert pedidos(client) == [str(pedido.id)]


def test_cobrar_pedido_sem_entrega_atrasada_responde_404(client: TestClient) -> None:
    cenario = preparar()
    no_prazo = atrasar(cenario, BOA_VISTA, (REGULAR, 120), prevista=HOJE)

    response = client.post(f"/pedidos/{no_prazo.id}/cobrancas", json={})

    assert response.status_code == 404
    assert cenario.cobrancas.listar(no_prazo.id) == []


def test_nova_previsao_antes_de_hoje_responde_422(client: TestClient) -> None:
    cenario = preparar()
    pedido = atrasar(cenario, BOA_VISTA, (REGULAR, 120))

    response = client.post(f"/pedidos/{pedido.id}/cobrancas", json={"nova_previsao": "2026-09-30"})

    assert response.status_code == 422
    assert cenario.cobrancas.listar(pedido.id) == []


def test_entrega_atrasada_fora_da_politica_nao_aparece(client: TestClient) -> None:
    cenario = preparar(motivos_de_alerta=(MotivoAlerta.ABAIXO_DO_PISO_ALERTA,))
    atrasar(cenario, BOA_VISTA, (REGULAR, 120), (URGENTE, 100))

    resultado = painel(client)

    assert resultado["entregas_atrasadas"] == []
    assert REGULAR.sku_code not in codigos(resultado["alertas"])
    [urgente] = [i for i in resultado["alertas"] if i["sku_code"] == URGENTE.sku_code]
    assert (urgente["motivos"], urgente["grupo"]) == (["abaixo_do_piso_alerta"], "em_ruptura")


def test_filtro_por_motivo_entrega_atrasada(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120))

    resultado = client.get("/painel", params={"motivo": "entrega_atrasada"}).json()

    assert codigos(resultado["alertas"]) == [REGULAR.sku_code]
    assert resultado["contagens"]["entregas_atrasadas"] == 1
    assert len(resultado["entregas_atrasadas"]) == 1
    assert entregas(client, motivo="abaixo_do_piso_alerta") == []


def test_sku_com_aviso_aparece_no_grupo_do_aviso_e_tambem_na_entrega(client: TestClient) -> None:
    cenario = preparar()
    atrasar(cenario, BOA_VISTA, (REGULAR, 120))
    avisar(client, REGULAR)

    resultado = painel(client)

    [item] = [i for i in resultado["alertas"] if i["sku_code"] == REGULAR.sku_code]
    assert item["grupo"] == "pedidos_de_vendas"
    assert item["motivos"] == ["entrega_atrasada"]
    assert [s["sku_code"] for s in resultado["entregas_atrasadas"][0]["pedidos"][0]["skus"]] == [REGULAR.sku_code]


def test_historico_de_atrasos_do_fornecedor(client: TestClient) -> None:
    cenario = preparar()
    for key, prevista, chegou in [
        ("atrasou-4", date(2026, 8, 10), datetime(2026, 8, 14, 15, 0, tzinfo=UTC)),
        ("atrasou-10", date(2026, 7, 1), datetime(2026, 7, 11, 9, 0, tzinfo=UTC)),
        ("no-prazo", date(2026, 9, 10), datetime(2026, 9, 9, 9, 0, tzinfo=UTC)),
    ]:
        cenario.erp.pedidos_compra.append(
            make_pedido_compra(BOA_VISTA, "recebido_total", key=key, data_prevista_entrega=prevista, recebido_em=chegou)
        )

    response = client.get(f"/fornecedores/{BOA_VISTA.id}/atrasos")

    assert response.status_code == 200
    historico = response.json()
    assert {k: v for k, v in historico.items() if k != "atrasos"} == {
        "fornecedor_id": str(BOA_VISTA.id),
        "fornecedor_nome": "Boa Vista Têxtil",
        "entregas_recebidas": 3,
        "entregas_atrasadas": 2,
        "media_dias_de_atraso": 7.0,
    }
    assert [(a["data_prevista_entrega"], a["dias_de_atraso"]) for a in historico["atrasos"]] == [
        ("2026-08-10", 4),
        ("2026-07-01", 10),
    ]


def test_historico_de_fornecedor_sem_entrega_recebida(client: TestClient) -> None:
    preparar()

    historico = client.get(f"/fornecedores/{KATRINA.id}/atrasos").json()

    assert (historico["entregas_recebidas"], historico["entregas_atrasadas"], historico["media_dias_de_atraso"]) == (
        0,
        0,
        None,
    )


def test_historico_de_fornecedor_inexistente_responde_404(client: TestClient) -> None:
    preparar()

    response = client.get("/fornecedores/00000000-0000-0000-0000-000000000000/atrasos")

    assert response.status_code == 404


def test_entregas_pendentes_do_sku_com_as_cobrancas(client: TestClient) -> None:
    cenario = preparar()
    atrasado = atrasar(cenario, BOA_VISTA, (REGULAR, 120), key="atrasado")
    no_prazo = atrasar(cenario, KATRINA, (REGULAR, 30), prevista=date(2026, 10, 20), key="no-prazo")
    primeira = cobrar(client, atrasado)
    cenario.relogio.avancar(days=1)
    segunda = cobrar(client, atrasado, nova_previsao="2026-10-08", comentario="Agora vai.")

    response = client.get(f"/skus/{REGULAR.sku_code}/entregas")

    assert response.status_code == 200
    assert response.json() == [
        {
            "pedido_id": str(atrasado.id),
            "fornecedor_nome": "Boa Vista Têxtil",
            "status": "enviado",
            "quantidade_pendente": 120,
            "data_prevista_entrega": "2026-09-30",
            "atrasada": True,
            "dias_de_atraso": 2,
            "cobranca_vigente": True,
            "cobrancas": [segunda, primeira],
        },
        {
            "pedido_id": str(no_prazo.id),
            "fornecedor_nome": "Katrina Têxtil",
            "status": "enviado",
            "quantidade_pendente": 30,
            "data_prevista_entrega": "2026-10-20",
            "atrasada": False,
            "dias_de_atraso": None,
            "cobranca_vigente": False,
            "cobrancas": [],
        },
    ]
    assert client.get(f"/skus/{ZERADO.sku_code}/entregas").json() == []
    assert client.get("/skus/NAO-EXISTE/entregas").status_code == 404
