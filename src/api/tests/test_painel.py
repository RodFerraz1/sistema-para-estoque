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
    client,  # noqa: F401 (fixture)
    codigos,
    montar_erp,
    painel,
    preparar,
)
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.politica_compra.schemas import PARAMETROS_V1, MotivoAlerta

def test_painel_traz_os_skus_com_motivo_na_ordem_de_urgencia(client: TestClient) -> None:
    preparar()

    resultado = painel(client)

    assert codigos(resultado["alertas"]) == [
        MAIS_URGENTE.sku_code,
        URGENTE.sku_code,
        PISO.sku_code,
        SEM_FORNECEDOR.sku_code,
    ]
    assert resultado["decididos"] == []
    assert resultado["skus_com_erro"] == [QUEBRADO.sku_code]


def test_item_traz_o_que_o_comprador_precisa_sem_abrir_o_sku(client: TestClient) -> None:
    preparar()

    _, urgente, piso, sem_fornecedor = painel(client)["alertas"]

    assert urgente == {
        "sku_code": URGENTE.sku_code,
        "produto_nome": "Toalha Banho Conforto",
        "cor": "branco",
        "tamanho": "70x140",
        "disponivel": 50,
        "cobertura_atual_meses": pytest.approx(0.5),
        "cobertura_na_chegada_sem_compra_meses": pytest.approx(-0.5),
        "motivos": ["ruptura_antes_da_chegada", "abaixo_do_piso_alerta"],
        "quantidade_sugerida": 300,
        "fornecedor_sugerido": "Boa Vista Têxtil",
        "avisos_abertos": 0,
        "ultimo_aviso": None,
        "so_por_aviso": False,
    }
    assert piso["motivos"] == ["abaixo_do_piso_alerta"]
    assert piso["cobertura_na_chegada_sem_compra_meses"] == pytest.approx(0.5)
    assert sem_fornecedor["motivos"] == ["abaixo_do_piso_alerta"]
    assert sem_fornecedor["cobertura_na_chegada_sem_compra_meses"] is None
    assert sem_fornecedor["quantidade_sugerida"] is None
    assert sem_fornecedor["fornecedor_sugerido"] is None


@pytest.mark.parametrize(
    ("motivos_de_alerta", "esperados"),
    [
        ((), []),
        ((MotivoAlerta.RUPTURA_ANTES_DA_CHEGADA,), [MAIS_URGENTE.sku_code, URGENTE.sku_code]),
        (
            (MotivoAlerta.ABAIXO_PEDIDO_MINIMO,),
            [MAIS_URGENTE.sku_code, URGENTE.sku_code, PISO.sku_code, REGULAR.sku_code],
        ),
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
        PARAMETROS_V1.model_copy(update={"motivos_de_alerta": (MotivoAlerta.ABAIXO_PEDIDO_MINIMO,)})
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
    assert len(resultado["alertas"]) == 4


def test_nada_pedindo_atencao_devolve_listas_vazias(client: TestClient) -> None:
    preparar(erp=montar_erp([SOBRANDO]))

    assert painel(client) == {"alertas": [], "decididos": [], "skus_com_erro": []}


class ERPForaDoAr(InMemoryERPAdapter):
    def listar_skus(self) -> list[SKU]:
        raise OperationalError("SELECT ...", {}, Exception("connection refused"))


def test_banco_fora_do_ar_responde_503_com_mensagem(client: TestClient) -> None:
    preparar(erp=ERPForaDoAr())

    response = client.get("/painel")

    assert response.status_code == 503
    assert "banco de dados está fora do ar" in response.json()["detail"]
