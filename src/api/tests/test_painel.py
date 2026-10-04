"""Testes HTTP de `/painel`. Cenário em `cenario_painel.py`."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.api.tests.cenario_painel import (
    INATIVO,
    MAIS_URGENTE,
    PISO,
    QUEBRADO,
    REGULAR,
    SEM_FORNECEDOR,
    SOBRANDO,
    URGENTE,
    ZERADO,
    client,  # noqa: F401 (fixture)
    codigos,
    montar_erp,
    painel,
    preparar,
)
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.politica_compra.schemas import PARAMETROS_V1, LeadTimeBase, MotivoAlerta

def test_painel_traz_os_skus_em_ruptura_do_zerado_ao_que_segura_mais_dias(client: TestClient) -> None:
    preparar()

    resultado = painel(client)

    assert codigos(resultado["alertas"]) == [
        ZERADO.sku_code,
        SEM_FORNECEDOR.sku_code,
        MAIS_URGENTE.sku_code,
        URGENTE.sku_code,
        PISO.sku_code,
    ]
    assert all(i["motivos"] == ["abaixo_do_piso_alerta"] for i in resultado["alertas"])
    assert resultado["decididos"] == []
    assert resultado["skus_com_erro"] == [QUEBRADO.sku_code]


def test_item_traz_o_que_o_comprador_precisa_sem_abrir_o_sku(client: TestClient) -> None:
    preparar()

    _, sem_fornecedor, _, urgente, piso = painel(client)["alertas"]

    # Sem lead time: 50 disponíveis, abaixo do piso de reposição de 100 (30 dias), compra
    # 100 * (30 / 30 + 2) - 50 = 250.
    assert urgente == {
        "sku_code": URGENTE.sku_code,
        "produto_nome": "Toalha Banho Conforto",
        "cor": "branco",
        "tamanho": "70x140",
        "disponivel": 50,
        "cobertura_atual_meses": pytest.approx(0.5),
        "cobertura_atual_dias": pytest.approx(15.0),
        "cobertura_na_chegada_sem_compra_meses": pytest.approx(0.5),
        "cobertura_na_chegada_sem_compra_dias": pytest.approx(15.0),
        "motivos": ["abaixo_do_piso_alerta"],
        "quantidade_sugerida": 250,
        "fornecedor_sugerido": "Boa Vista Têxtil",
        "avisos_abertos": 0,
        "ultimo_aviso": None,
        "so_por_aviso": False,
        "grupo": "em_ruptura",
        "parou_de_vender": False,
    }
    # Posição de 150 com o que está a caminho: acima do piso de reposição, não compra.
    assert piso["cobertura_atual_dias"] == pytest.approx(15.0)
    assert piso["cobertura_na_chegada_sem_compra_dias"] == pytest.approx(45.0)
    assert piso["quantidade_sugerida"] is None
    assert sem_fornecedor["cobertura_atual_dias"] == pytest.approx(3.0)
    assert sem_fornecedor["cobertura_na_chegada_sem_compra_meses"] is None
    assert sem_fornecedor["cobertura_na_chegada_sem_compra_dias"] is None
    assert sem_fornecedor["quantidade_sugerida"] is None
    assert sem_fornecedor["fornecedor_sugerido"] is None


def test_sku_que_segura_os_dias_do_piso_nao_esta_em_ruptura(client: TestClient) -> None:
    preparar(piso_alerta_dias=15)

    alertas = codigos(painel(client)["alertas"])

    assert alertas == [ZERADO.sku_code, SEM_FORNECEDOR.sku_code, MAIS_URGENTE.sku_code]


def test_lead_time_ignorado_nunca_gera_ruptura_antes_da_chegada(client: TestClient) -> None:
    preparar(motivos_de_alerta=tuple(MotivoAlerta))

    alertas = painel(client)["alertas"]

    assert alertas
    assert all("ruptura_antes_da_chegada" not in i["motivos"] for i in alertas)


def test_politica_gravada_com_lead_time_observado_calcula_como_antes(client: TestClient) -> None:
    preparar(
        lead_time_base=LeadTimeBase.OBSERVADO,
        motivos_de_alerta=(MotivoAlerta.RUPTURA_ANTES_DA_CHEGADA, MotivoAlerta.ABAIXO_DO_PISO_ALERTA),
    )

    alertas = {i["sku_code"]: i for i in painel(client)["alertas"]}

    # Lead time de 30 dias consome 100: na chegada sobra 0 de 50, e a compra é 300 - 0.
    urgente = alertas[URGENTE.sku_code]
    assert urgente["motivos"] == ["ruptura_antes_da_chegada", "abaixo_do_piso_alerta"]
    assert urgente["cobertura_na_chegada_sem_compra_meses"] == pytest.approx(-0.5)
    assert urgente["cobertura_na_chegada_sem_compra_dias"] == pytest.approx(-15.0)
    assert urgente["quantidade_sugerida"] == 300
    assert alertas[PISO.sku_code]["motivos"] == ["abaixo_do_piso_alerta"]
    assert alertas[PISO.sku_code]["quantidade_sugerida"] == 250


@pytest.mark.parametrize(
    ("motivos_de_alerta", "esperados"),
    [
        ((), []),
        (
            (MotivoAlerta.ABAIXO_DO_PISO_ALERTA,),
            [ZERADO.sku_code, SEM_FORNECEDOR.sku_code, MAIS_URGENTE.sku_code, URGENTE.sku_code, PISO.sku_code],
        ),
        ((MotivoAlerta.ABAIXO_PEDIDO_MINIMO,), [ZERADO.sku_code, MAIS_URGENTE.sku_code, URGENTE.sku_code]),
    ],
    ids=["nenhum-motivo", "so-ruptura", "pedido-minimo"],
)
def test_so_os_motivos_da_politica_poem_o_sku_no_painel(
    client: TestClient, motivos_de_alerta: tuple[MotivoAlerta, ...], esperados: list[str]
) -> None:
    preparar(motivos_de_alerta=motivos_de_alerta)

    alertas = painel(client)["alertas"]

    assert sorted(codigos(alertas)) == sorted(esperados)
    assert all(set(i["motivos"]) <= set(motivos_de_alerta) for i in alertas)


def test_mudar_a_politica_muda_o_painel_na_proxima_vez(client: TestClient) -> None:
    cenario = preparar()
    assert REGULAR.sku_code not in codigos(painel(client)["alertas"])

    cenario.politicas.salvar_nova_versao(
        PARAMETROS_V1.model_copy(
            update={"lead_time_base": LeadTimeBase.OBSERVADO, "motivos_de_alerta": (MotivoAlerta.ABAIXO_PEDIDO_MINIMO,)}
        )
    )

    assert REGULAR.sku_code in codigos(painel(client)["alertas"])


def test_sku_inativo_nunca_aparece(client: TestClient) -> None:
    preparar(motivos_de_alerta=tuple(MotivoAlerta))

    resultado = painel(client)

    assert INATIVO.sku_code not in codigos(resultado["alertas"])
    assert INATIVO.sku_code not in resultado["skus_com_erro"]


def test_sku_sem_estoque_vai_para_skus_com_erro_sem_derrubar_o_painel(client: TestClient) -> None:
    preparar()

    resultado = painel(client)

    assert resultado["skus_com_erro"] == [QUEBRADO.sku_code]
    assert len(resultado["alertas"]) == 5


def test_nada_pedindo_atencao_devolve_listas_vazias(client: TestClient) -> None:
    preparar(erp=montar_erp([SOBRANDO]))

    assert painel(client) == {
        "alertas": [],
        "decididos": [],
        "skus_com_erro": [],
        "contagens": {
            "pedidos_de_vendas": 0,
            "entregas_atrasadas": 0,
            "em_ruptura": 0,
            "vao_faltar": 0,
            "outros_alertas": 0,
        },
        "entregas_atrasadas": [],
    }


class ERPForaDoAr(InMemoryERPAdapter):
    def listar_skus(self) -> list[SKU]:
        raise OperationalError("SELECT ...", {}, Exception("connection refused"))


def test_banco_fora_do_ar_responde_503_com_mensagem(client: TestClient) -> None:
    preparar(erp=ERPForaDoAr())

    response = client.get("/painel")

    assert response.status_code == 503
    assert "banco de dados está fora do ar" in response.json()["detail"]
