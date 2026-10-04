"""Testes HTTP da tela de Estoque (`GET /estoque`). Cenário em `cenario_painel.py`, com a
política padrão (piso de alerta de 20 dias) e venda de 100 por mês (10 por 3 dias) em todos
os SKUs com venda. `CAMPEAO` vende 300 por mês e `NOVO` nunca vendeu."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    MAIS_URGENTE,
    PISO,
    REGULAR,
    SEM_FORNECEDOR,
    SOBRANDO,
    URGENTE,
    ZERADO,
    Cenario,
    client,  # noqa: F401 (fixture)
    codigos,
    meses_fechados,
    preparar,
)
from tests.fakes import make_estoque, make_sku, make_venda

CAMPEAO = make_sku("TBC-AMAR-70140-01", produto_nome="Toalha Banho Conforto", cor="amarelo")
NOVO = make_sku("JC-CINZ-CASAL-01", produto_nome="Jogo de Cama Percal", categoria="jogo_cama", tamanho="casal")


def preparar_estoque(piso_alerta_dias: int | None = None) -> Cenario:
    cenario = preparar(piso_alerta_dias=piso_alerta_dias) if piso_alerta_dias else preparar()
    cenario.erp.skus += [CAMPEAO, NOVO]
    cenario.erp.estoques_por_sku[CAMPEAO.sku_code] = make_estoque(disponivel=300)
    cenario.erp.estoques_por_sku[NOVO.sku_code] = make_estoque(disponivel=40)
    cenario.erp.vendas += [
        make_venda(CAMPEAO, data, 300, key=f"{CAMPEAO.sku_code}-{data:%Y-%m}") for data in meses_fechados(6)
    ]
    return cenario


def estoque(client: TestClient, **parametros: str | int) -> dict:
    response = client.get("/estoque", params=parametros)
    assert response.status_code == 200, response.text
    return response.json()


POR_COBERTURA = [
    ZERADO,
    SEM_FORNECEDOR,
    MAIS_URGENTE,
    URGENTE,
    PISO,
    CAMPEAO,
    REGULAR,
    SOBRANDO,
    NOVO,
]


def test_lista_todos_os_skus_ativos_com_estoque_pela_cobertura_e_os_sem_venda_no_fim(client: TestClient) -> None:
    preparar_estoque()

    resultado = estoque(client)

    assert codigos(resultado["itens"]) == [s.sku_code for s in POR_COBERTURA]
    assert resultado["total"] == 9
    assert resultado["pagina"] == 1


def test_linha_traz_o_que_o_comprador_tira_do_erp(client: TestClient) -> None:
    preparar_estoque()

    itens = {i["sku_code"]: i for i in estoque(client)["itens"]}

    assert itens[PISO.sku_code] == {
        "sku_code": PISO.sku_code,
        "produto_nome": "Toalha Banho Conforto",
        "cor": "rosa",
        "tamanho": "70x140",
        "categoria": "felpudo",
        "disponivel": 50,
        "em_transito": 100,
        "venda_media_diaria": pytest.approx(100 / 30),
        "cobertura_dias": pytest.approx(15.0),
        "em_ruptura": True,
    }
    assert itens[NOVO.sku_code]["venda_media_diaria"] == 0
    assert itens[NOVO.sku_code]["cobertura_dias"] is None
    assert itens[NOVO.sku_code]["em_ruptura"] is False
    assert itens[REGULAR.sku_code]["em_ruptura"] is False


@pytest.mark.parametrize(
    ("situacao", "esperados"),
    [
        ("em_ruptura", [ZERADO, SEM_FORNECEDOR, MAIS_URGENTE, URGENTE, PISO]),
        ("sem_venda", [NOVO]),
        ("com_transito", [PISO]),
    ],
)
def test_filtra_pela_situacao(client: TestClient, situacao: str, esperados: list) -> None:
    preparar_estoque()

    resultado = estoque(client, situacao=situacao)

    assert codigos(resultado["itens"]) == [s.sku_code for s in esperados]
    assert resultado["total"] == len(esperados)


def test_ruptura_segue_o_piso_de_alerta_da_politica_ativa(client: TestClient) -> None:
    preparar_estoque(piso_alerta_dias=5)

    assert codigos(estoque(client, situacao="em_ruptura")["itens"]) == [ZERADO.sku_code, SEM_FORNECEDOR.sku_code]


@pytest.mark.parametrize(
    ("ordem", "primeiros"),
    [
        ("cobertura", [ZERADO, SEM_FORNECEDOR, MAIS_URGENTE]),
        ("venda_diaria", [CAMPEAO, SEM_FORNECEDOR, MAIS_URGENTE]),
        ("nome", [NOVO, SEM_FORNECEDOR, CAMPEAO]),
    ],
)
def test_ordena_pela_cobertura_pela_venda_diaria_ou_pelo_nome(client: TestClient, ordem: str, primeiros: list) -> None:
    preparar_estoque()

    itens = estoque(client, ordem=ordem)["itens"]

    assert codigos(itens)[:3] == [s.sku_code for s in primeiros]
    assert len(itens) == 9


def test_pela_venda_diaria_quem_nao_vende_fica_no_fim(client: TestClient) -> None:
    preparar_estoque()

    assert codigos(estoque(client, ordem="venda_diaria")["itens"])[-1] == NOVO.sku_code


def test_busca_e_categoria_usam_a_regra_do_painel(client: TestClient) -> None:
    preparar_estoque()

    assert codigos(estoque(client, busca="toalha AMARELO")["itens"]) == [CAMPEAO.sku_code]
    assert codigos(estoque(client, busca="lencol")["itens"]) == [SEM_FORNECEDOR.sku_code]
    assert codigos(estoque(client, categoria="jogo_cama")["itens"]) == [NOVO.sku_code]
    assert estoque(client, busca="toalha", situacao="com_transito", categoria="felpudo")["total"] == 1


def test_pagina_os_skus_na_mesma_ordem(client: TestClient) -> None:
    preparar_estoque()

    paginas = [estoque(client, pagina=p, por_pagina=4) for p in (1, 2, 3)]

    assert [codigos(p["itens"]) for p in paginas] == [
        [s.sku_code for s in POR_COBERTURA[:4]],
        [s.sku_code for s in POR_COBERTURA[4:8]],
        [NOVO.sku_code],
    ]
    assert {p["total"] for p in paginas} == {9}
    assert [p["pagina"] for p in paginas] == [1, 2, 3]
    assert {p["por_pagina"] for p in paginas} == {4}


def test_pagina_depois_da_ultima_vem_vazia_com_o_total(client: TestClient) -> None:
    preparar_estoque()

    resultado = estoque(client, pagina=4, por_pagina=4)

    assert resultado["itens"] == []
    assert resultado["total"] == 9


def test_por_pagina_padrao_e_50_e_aceita_ate_100(client: TestClient) -> None:
    preparar_estoque()

    assert estoque(client)["por_pagina"] == 50
    assert estoque(client, por_pagina=100)["por_pagina"] == 100


@pytest.mark.parametrize(
    "parametros",
    [
        {"por_pagina": 101},
        {"por_pagina": 0},
        {"pagina": 0},
        {"situacao": "qualquer"},
        {"ordem": "preco"},
    ],
)
def test_parametro_invalido_responde_422(client: TestClient, parametros: dict) -> None:
    preparar_estoque()

    assert client.get("/estoque", params=parametros).status_code == 422


def test_nenhum_sku_com_os_filtros(client: TestClient) -> None:
    preparar_estoque()

    assert estoque(client, busca="nao existe") == {"itens": [], "total": 0, "pagina": 1, "por_pagina": 50}


@pytest.mark.parametrize(
    "papel",
    [pytest.param(p, marks=pytest.mark.papeis(p)) for p in ("vendas", "reposicao", "admin")],
)
def test_so_o_comprador_ve_o_estoque(client: TestClient, papel: str) -> None:
    preparar_estoque()

    assert client.get("/estoque").status_code == 403
