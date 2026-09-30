"""Faixa de aprovação: limites pelo valor e as exceções de `politicas/aprovacao-compras.md`."""
from __future__ import annotations

import pytest

from src.politica_compra.schemas import PARAMETROS_V1
from src.purchasing.faixa import faixa_aprovacao
from src.purchasing.schemas import FaixaAprovacao


def _reais(valor: int) -> int:
    return valor * 100


def _faixa(valor_centavos: int, *, viola_teto: bool) -> int:
    return faixa_aprovacao(
        valor_centavos, viola_teto=viola_teto, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    ).faixa


# Sem violação de teto a reposição regular desce uma faixa; com violação, sobe uma.
@pytest.mark.parametrize(
    ("valor_centavos", "sem_violacao", "com_violacao"),
    [
        (0, 1, 2),
        (_reais(15_000), 1, 2),
        (_reais(15_000) + 1, 1, 3),
        (_reais(60_000), 1, 3),
        (_reais(60_000) + 1, 2, 4),
        (_reais(150_000), 2, 4),
        (_reais(150_000) + 1, 3, 4),
    ],
)
def test_limites_das_faixas_sao_inclusivos(
    valor_centavos: int, sem_violacao: int, com_violacao: int
) -> None:
    assert _faixa(valor_centavos, viola_teto=False) == sem_violacao
    assert _faixa(valor_centavos, viola_teto=True) == com_violacao


def test_limites_vem_da_politica() -> None:
    parametros = PARAMETROS_V1.model_copy(
        update={"faixa_1_ate_reais": 1_000, "faixa_2_ate_reais": 2_000, "faixa_3_ate_reais": 3_000}
    )

    resultado = faixa_aprovacao(
        _reais(2_500), viola_teto=False, fornecedor_tem_pedido=True, parametros=parametros
    )

    assert resultado.faixa == 2


def test_reposicao_regular_desce_uma_faixa() -> None:
    resultado = faixa_aprovacao(
        _reais(40_000), viola_teto=False, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    )

    assert resultado == FaixaAprovacao(
        faixa=1,
        aprovadores="comprador chefe",
        exige_justificativa=False,
        ajustes=["Reposição regular de SKU, dentro da política de estoque: desce da faixa 2 para a 1."],
    )


def test_reposicao_regular_nao_desce_abaixo_da_faixa_1() -> None:
    resultado = faixa_aprovacao(
        _reais(5_000), viola_teto=False, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == 1
    assert resultado.ajustes == []


def test_violacao_de_teto_sobe_uma_faixa() -> None:
    resultado = faixa_aprovacao(
        _reais(40_000), viola_teto=True, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    )

    assert resultado == FaixaAprovacao(
        faixa=3,
        aprovadores="comprador chefe + gerente comercial + sócio financeiro",
        exige_justificativa=True,
        ajustes=["Viola o teto da política de estoque: sobe da faixa 2 para a 3."],
    )


def test_violacao_de_teto_nao_passa_da_faixa_4() -> None:
    resultado = faixa_aprovacao(
        _reais(200_000), viola_teto=True, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == 4
    assert resultado.ajustes == []


def test_fornecedor_sem_pedido_vai_no_minimo_para_a_faixa_3() -> None:
    resultado = faixa_aprovacao(
        _reais(5_000), viola_teto=False, fornecedor_tem_pedido=False, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == 3
    assert resultado.ajustes == [
        "Primeiro pedido com o fornecedor: no mínimo faixa 3, sobe da faixa 1 para a 3."
    ]


def test_fornecedor_sem_pedido_nao_desce_quem_ja_esta_acima_da_3() -> None:
    resultado = faixa_aprovacao(
        _reais(200_000), viola_teto=False, fornecedor_tem_pedido=False, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == 3
    assert resultado.ajustes == [
        "Reposição regular de SKU, dentro da política de estoque: desce da faixa 4 para a 3."
    ]


def test_fornecedor_sem_pedido_com_violacao_de_teto() -> None:
    resultado = faixa_aprovacao(
        _reais(200_000), viola_teto=True, fornecedor_tem_pedido=False, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == 4
    assert resultado.aprovadores == (
        "comprador chefe + gerente comercial + sócio financeiro, com reunião de compra registrada"
    )


@pytest.mark.parametrize(
    ("valor_reais", "viola_teto", "faixa", "aprovadores", "exige_justificativa"),
    [
        (5_000, False, 1, "comprador chefe", False),
        (100_000, False, 2, "comprador chefe + gerente comercial ou sócio financeiro", True),
        (40_000, True, 3, "comprador chefe + gerente comercial + sócio financeiro", True),
        (
            100_000,
            True,
            4,
            "comprador chefe + gerente comercial + sócio financeiro, com reunião de compra registrada",
            True,
        ),
    ],
)
def test_aprovadores_e_justificativa_por_faixa(
    valor_reais: int, viola_teto: bool, faixa: int, aprovadores: str, exige_justificativa: bool
) -> None:
    resultado = faixa_aprovacao(
        _reais(valor_reais), viola_teto=viola_teto, fornecedor_tem_pedido=True, parametros=PARAMETROS_V1
    )

    assert resultado.faixa == faixa
    assert resultado.aprovadores == aprovadores
    assert resultado.exige_justificativa is exige_justificativa
