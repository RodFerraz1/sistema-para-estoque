"""Testes HTTP da busca e dos filtros de `/painel` e de `/categorias` e `/fornecedores`.
Cenário em `cenario_painel.py`: sem filtro, o painel tem `ZERADO`, `SEM_FORNECEDOR`,
`MAIS_URGENTE`, `URGENTE` e `PISO` em ruptura."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    BOA_VISTA,
    KATRINA,
    MAIS_URGENTE,
    PISO,
    REGULAR,
    SEM_FORNECEDOR,
    URGENTE,
    ZERADO,
    avisar,
    client,  # noqa: F401 (fixture)
    codigos,
    decidir,
    preparar,
)
from src.politica_compra.schemas import LeadTimeBase, MotivoAlerta

SEM_NADA = {
    "pedidos_de_vendas": 0,
    "estoque_divergente": 0,
    "entregas_atrasadas": 0,
    "em_ruptura": 0,
    "vao_faltar": 0,
    "outros_alertas": 0,
}


def painel(client: TestClient, **filtros: str) -> dict:
    response = client.get("/painel", params=filtros)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("busca", "esperados"),
    [
        ("LILAS", [ZERADO]),
        ("toalha azul", [MAIS_URGENTE]),
        ("lc-bran", [SEM_FORNECEDOR]),
        ("casal", [SEM_FORNECEDOR]),
        ("  Lençol   CASAL ", [SEM_FORNECEDOR]),
        ("toalha", [ZERADO, MAIS_URGENTE, URGENTE, PISO]),
        ("toalha casal", []),
    ],
)
def test_busca_acha_pelo_codigo_nome_cor_e_tamanho_sem_acento_nem_maiuscula(
    client: TestClient, busca: str, esperados: list
) -> None:
    preparar()

    assert codigos(painel(client, busca=busca)["alertas"]) == [s.sku_code for s in esperados]


def test_busca_vazia_nao_filtra(client: TestClient) -> None:
    preparar()

    assert len(painel(client, busca="   ")["alertas"]) == 5


def test_filtra_por_categoria(client: TestClient) -> None:
    preparar()

    assert codigos(painel(client, categoria="cama")["alertas"]) == [SEM_FORNECEDOR.sku_code]
    assert len(painel(client, categoria="felpudo")["alertas"]) == 4
    assert painel(client, categoria="mesa")["alertas"] == []


def test_filtra_por_fornecedor_que_vende_o_sku(client: TestClient) -> None:
    preparar()

    assert codigos(painel(client, fornecedor=str(KATRINA.id))["alertas"]) == [
        ZERADO.sku_code,
        MAIS_URGENTE.sku_code,
    ]
    assert SEM_FORNECEDOR.sku_code not in codigos(painel(client, fornecedor=str(BOA_VISTA.id))["alertas"])


def test_filtra_por_aviso_da_equipe_de_vendas(client: TestClient) -> None:
    preparar()
    avisar(client, URGENTE)
    avisar(client, REGULAR)

    assert codigos(painel(client, motivo="aviso")["alertas"]) == [URGENTE.sku_code, REGULAR.sku_code]


def test_filtro_por_motivo_traz_quem_tem_o_motivo_mesmo_no_grupo_dos_avisos(client: TestClient) -> None:
    preparar()
    avisar(client, URGENTE)
    avisar(client, REGULAR)

    resultado = painel(client, motivo="abaixo_do_piso_alerta")

    assert codigos(resultado["alertas"]) == [
        URGENTE.sku_code,
        ZERADO.sku_code,
        SEM_FORNECEDOR.sku_code,
        MAIS_URGENTE.sku_code,
        PISO.sku_code,
    ]
    assert painel(client, motivo="ruptura_antes_da_chegada")["alertas"] == []


def test_motivo_desconhecido_responde_422(client: TestClient) -> None:
    preparar()

    assert client.get("/painel", params={"motivo": "qualquer"}).status_code == 422


def test_filtros_combinados_valem_juntos(client: TestClient) -> None:
    preparar()
    avisar(client, MAIS_URGENTE)
    avisar(client, URGENTE)

    resultado = painel(client, busca="toalha", categoria="felpudo", motivo="aviso", fornecedor=str(KATRINA.id))

    assert codigos(resultado["alertas"]) == [MAIS_URGENTE.sku_code]


def test_cada_item_diz_o_seu_grupo_e_o_painel_conta_os_skus_de_cada_grupo(client: TestClient) -> None:
    preparar()
    avisar(client, URGENTE)

    resultado = painel(client)

    assert [(i["sku_code"], i["grupo"]) for i in resultado["alertas"][:2]] == [
        (URGENTE.sku_code, "pedidos_de_vendas"),
        (ZERADO.sku_code, "em_ruptura"),
    ]
    assert resultado["contagens"] == {**SEM_NADA, "pedidos_de_vendas": 1, "em_ruptura": 4}


def test_contagens_seguem_o_filtro(client: TestClient) -> None:
    preparar()
    avisar(client, ZERADO)

    assert painel(client, fornecedor=str(KATRINA.id))["contagens"] == {
        **SEM_NADA,
        "pedidos_de_vendas": 1,
        "em_ruptura": 1,
    }
    assert painel(client, categoria="cama")["contagens"] == {**SEM_NADA, "em_ruptura": 1}


def test_lead_time_ligado_conta_o_grupo_dos_que_vao_faltar(client: TestClient) -> None:
    preparar(
        lead_time_base=LeadTimeBase.OBSERVADO,
        motivos_de_alerta=[MotivoAlerta.RUPTURA_ANTES_DA_CHEGADA],
    )

    resultado = painel(client, busca="toalha")

    assert resultado["contagens"] == {**SEM_NADA, "vao_faltar": 3}
    assert {i["grupo"] for i in resultado["alertas"]} == {"vao_faltar"}


def test_nenhum_sku_com_os_filtros_devolve_tudo_vazio(client: TestClient) -> None:
    preparar()
    decidir(client, URGENTE)

    resultado = painel(client, busca="nao existe")

    assert resultado["alertas"] == []
    assert resultado["decididos"] == []
    assert resultado["contagens"] == SEM_NADA


def test_decididos_seguem_a_busca_a_categoria_e_o_fornecedor(client: TestClient) -> None:
    preparar()
    decidir(client, ZERADO)
    decidir(client, SEM_FORNECEDOR)

    assert codigos(painel(client, categoria="cama")["decididos"]) == [SEM_FORNECEDOR.sku_code]
    assert codigos(painel(client, busca="lilás")["decididos"]) == [ZERADO.sku_code]
    assert codigos(painel(client, fornecedor=str(KATRINA.id))["decididos"]) == [ZERADO.sku_code]
    assert len(painel(client, motivo="aviso")["decididos"]) == 2


def test_categorias_sao_as_que_tem_sku_ativo(client: TestClient) -> None:
    preparar()

    response = client.get("/categorias")

    assert response.status_code == 200
    assert response.json() == ["cama", "felpudo"]


def test_fornecedores_sao_os_que_vendem_algum_sku_ativo_por_nome(client: TestClient) -> None:
    preparar()

    response = client.get("/fornecedores")

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(BOA_VISTA.id), "nome": "Boa Vista Têxtil"},
        {"id": str(KATRINA.id), "nome": "Katrina Têxtil"},
    ]
