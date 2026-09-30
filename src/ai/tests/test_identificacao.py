"""Testes da identificação dos SKUs de uma pergunta do chat."""
from __future__ import annotations

import pytest

from src.ai.identificacao import (
    LIMIAR_PRODUTO,
    MAX_SKUS_POR_RESPOSTA,
    identificar_skus,
    produtos_do_catalogo,
)
from src.ai.schemas import NENHUM_PRODUTO
from tests.fakes import make_entendimento, make_sku, uid

CONFORTO = "Toalha Banho Conforto"
PREMIUM = "Toalha Banho Premium"
PERCAL = "Jogo de Cama Percal 200 fios"
EDREDOM = "Edredom Duplaface"

CATALOGO = produtos_do_catalogo(
    [
        make_sku("TBC-BEGE-70140-01", produto_nome=CONFORTO, cor="bege", tamanho="70x140"),
        make_sku("TBC-BEGE-70140-02", produto_nome=CONFORTO, cor="bege", tamanho="70x140"),
        make_sku("TBC-BRAN-70140-03", produto_nome=CONFORTO, cor="branco", tamanho="70x140"),
        make_sku("TBC-AZUL-70140-07", produto_nome=CONFORTO, cor="azul", tamanho="70x140"),
        make_sku("TBP-AZUL-80150-07", produto_nome=PREMIUM, cor="azul-marinho", tamanho="80x150"),
        make_sku("TBP-GRAF-80150-03", produto_nome=PREMIUM, cor="grafite", tamanho="80x150"),
        make_sku("JDCP-BRAN-CASAL-02", produto_nome=PERCAL, categoria="jogo_cama", cor="branco", tamanho="casal"),
        make_sku("JDCP-BRAN-QUEEN-03", produto_nome=PERCAL, categoria="jogo_cama", cor="branco", tamanho="queen"),
        make_sku("JDCP-BEGE-CASAL-05", produto_nome=PERCAL, categoria="jogo_cama", cor="bege", tamanho="casal"),
        make_sku("ED-BEGE-CASAL-01", produto_nome=EDREDOM, categoria="jogo_cama", cor="bege/marrom", tamanho="casal"),
        make_sku("ED-CINZ-QUEEN-04", produto_nome=EDREDOM, categoria="jogo_cama", cor="cinza/branco", tamanho="queen"),
        make_sku("CB-OFF--CASAL-08", produto_nome="Colcha Bouti", categoria="jogo_cama", cor="off-white", tamanho="casal"),
        make_sku("LT-AZUL-ÚNICO-03", produto_nome="Luva Térmica", categoria="cozinha", cor="azul", tamanho="único"),
    ]
)


def identificar(pergunta: str, produto: str = NENHUM_PRODUTO, confianca: float = 0.95, **kwargs):
    entendimento = make_entendimento(produto=produto, confianca_produto=confianca, **kwargs)
    return identificar_skus(pergunta, entendimento, CATALOGO)


def test_produtos_agrupam_os_skus_com_cores_e_tamanhos_sem_repeticao() -> None:
    percal = next(p for p in CATALOGO if p.nome == PERCAL)

    assert percal.categoria == "jogo_cama"
    assert percal.cores == ["bege", "branco"]
    assert percal.tamanhos == ["casal", "queen"]
    assert percal.prefixo == "JDCP"
    assert [s.sku_code for s in percal.skus] == ["JDCP-BEGE-CASAL-05", "JDCP-BRAN-CASAL-02", "JDCP-BRAN-QUEEN-03"]


def test_nome_de_produto_repetido_ganha_sufixo() -> None:
    outra_toalha = make_sku("B-01", produto_nome="Toalha").model_copy(update={"produto_id": uid("produto", "B")})

    produtos = produtos_do_catalogo([make_sku("A-01", produto_nome="Toalha"), outra_toalha])

    assert [p.nome for p in produtos] == ["Toalha", "Toalha (2)"]


def test_codigo_na_pergunta_ganha_do_produto() -> None:
    identificacao = identificar("Qual a situação do SKU TBC-BEGE-70140-01?", produto=PERCAL)

    assert identificacao.skus == ["TBC-BEGE-70140-01"]
    assert identificacao.origem == "codigo"
    assert identificacao.produto is None


@pytest.mark.parametrize(
    ("pergunta", "sku"),
    [
        ("como está a cb-off--casal-08?", "CB-OFF--CASAL-08"),
        ("e a LT-AZUL-ÚNICO-03", "LT-AZUL-ÚNICO-03"),
        ("e a lt-azul-unico-03", "LT-AZUL-ÚNICO-03"),
    ],
)
def test_codigo_com_hifen_duplo_ou_acento_sem_diferenciar_caixa(pergunta: str, sku: str) -> None:
    assert identificar(pergunta).skus == [sku]


def test_codigo_so_casa_como_palavra_inteira() -> None:
    assert identificar("e o TBC-BEGE-70140-012?").origem == "nenhum"


def test_dois_codigos_na_pergunta() -> None:
    identificacao = identificar("compare TBC-BRAN-70140-03 e ED-CINZ-QUEEN-04")

    assert sorted(identificacao.skus) == ["ED-CINZ-QUEEN-04", "TBC-BRAN-70140-03"]
    assert identificacao.origem == "codigo"


def test_produto_sem_cor_nem_tamanho_traz_todos_os_skus() -> None:
    identificacao = identificar("como tá a toalha banho conforto?", produto=CONFORTO)

    assert identificacao.skus == ["TBC-AZUL-70140-07", "TBC-BEGE-70140-01", "TBC-BEGE-70140-02", "TBC-BRAN-70140-03"]
    assert identificacao.origem == "produto"
    assert identificacao.produto == CONFORTO
    assert identificacao.candidatos == []


def test_produto_no_limiar_e_usado() -> None:
    assert identificar("toalha conforto", produto=CONFORTO, confianca=LIMIAR_PRODUTO).origem == "produto"


def test_produto_abaixo_do_limiar_vira_nenhum_com_os_candidatos() -> None:
    identificacao = identificar(
        "e a toalha?",
        produto=CONFORTO,
        confianca=LIMIAR_PRODUTO - 0.01,
        probabilidades_produto={
            CONFORTO: 0.40,
            NENHUM_PRODUTO: 0.25,
            PREMIUM: 0.20,
            PERCAL: 0.14,
            EDREDOM: 0.01,
        },
    )

    assert identificacao.skus == []
    assert identificacao.origem == "nenhum"
    assert identificacao.produto is None
    assert identificacao.candidatos == [CONFORTO, PREMIUM]


def test_candidatos_sao_no_maximo_tres() -> None:
    identificacao = identificar(
        "e a toalha?",
        produto=CONFORTO,
        confianca=0.1,
        probabilidades_produto={CONFORTO: 0.3, PREMIUM: 0.25, PERCAL: 0.2, EDREDOM: 0.25},
    )

    assert identificacao.candidatos == [CONFORTO, PREMIUM, EDREDOM]


def test_produto_nenhum_nao_identifica_sku() -> None:
    identificacao = identificar("vai chover amanhã?")

    assert (identificacao.skus, identificacao.origem, identificacao.candidatos) == ([], "nenhum", [])


@pytest.mark.parametrize(
    ("pergunta", "produto", "skus"),
    [
        ("toalha conforto branca", CONFORTO, ["TBC-BRAN-70140-03"]),
        ("toalhas conforto BEGES", CONFORTO, ["TBC-BEGE-70140-01", "TBC-BEGE-70140-02"]),
        ("edredom marrom", EDREDOM, ["ED-BEGE-CASAL-01"]),
        ("toalha premium azul", PREMIUM, ["TBP-AZUL-80150-07"]),
        ("percal queen", PERCAL, ["JDCP-BRAN-QUEEN-03"]),
        ("percal branco casal", PERCAL, ["JDCP-BRAN-CASAL-02"]),
    ],
)
def test_estreita_pela_cor_e_pelo_tamanho_citados(pergunta: str, produto: str, skus: list[str]) -> None:
    assert identificar(pergunta, produto=produto).skus == skus


def test_filtro_que_nao_casa_e_ignorado() -> None:
    assert identificar("percal verde queen", produto=PERCAL).skus == ["JDCP-BRAN-QUEEN-03"]
    assert identificar("percal verde king", produto=PERCAL).skus == [
        "JDCP-BEGE-CASAL-05",
        "JDCP-BRAN-CASAL-02",
        "JDCP-BRAN-QUEEN-03",
    ]


def test_lista_acima_do_maximo_e_cortada() -> None:
    total = MAX_SKUS_POR_RESPOSTA + 3
    produtos = produtos_do_catalogo(
        [make_sku(f"PM-{i:02d}", produto_nome="Pano Multiuso", cor=f"cor{i}") for i in range(total)]
    )

    identificacao = identificar_skus(
        "pano multiuso", make_entendimento(produto="Pano Multiuso"), produtos
    )

    assert identificacao.skus == [f"PM-{i:02d}" for i in range(MAX_SKUS_POR_RESPOSTA)]
    assert identificacao.total_skus == total
