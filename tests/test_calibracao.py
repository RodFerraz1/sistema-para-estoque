"""Regra de calibração dos limiares do M8, com probabilidades de exemplo."""
from __future__ import annotations

import pytest

from scripts.calibracao import calibrar, calibrar_erro_critico, descrever, formatar_limiar


def test_sem_3_positivos_e_3_negativos_o_limiar_atual_fica() -> None:
    calibracao = calibrar([0.95, 0.90], [0.10, 0.20, 0.30], atual=0.60)

    assert calibracao.limiar == 0.60
    assert calibracao.regra == "amostra_insuficiente"
    assert calibracao.folga is None
    assert "2 positivos e 3 negativos" in calibracao.motivo


def test_separavel_e_o_multiplo_de_0_05_mais_perto_do_ponto_medio() -> None:
    calibracao = calibrar([0.94, 0.96, 0.98], [0.67, 0.13, 0.09], atual=0.90)

    assert (calibracao.limiar, calibracao.regra, calibracao.atual) == (0.80, "ponto_medio", 0.90)
    assert calibracao.lados == (0.67, 0.94)
    assert calibracao.folga == (0.13, 0.14)


def test_separavel_sem_multiplo_de_0_05_entre_os_lados_fica_o_ponto_medio_com_duas_casas() -> None:
    calibracao = calibrar([0.74, 0.80, 0.90], [0.71, 0.20, 0.10], atual=0.50)

    assert calibracao.limiar == 0.72
    assert calibracao.regra == "ponto_medio"


def test_ponto_medio_com_duas_casas_que_cairia_num_lado_ganha_a_terceira_casa() -> None:
    assert calibrar([0.71, 0.80, 0.90], [0.70, 0.20, 0.10], atual=0.50).limiar == 0.705


def test_ponto_medio_a_mesma_distancia_de_dois_multiplos_fica_com_o_maior() -> None:
    assert calibrar([0.78, 0.80, 0.90], [0.67, 0.20, 0.10], atual=0.50).limiar == 0.75


def test_nao_separavel_e_o_meio_da_faixa_de_mais_acertos() -> None:
    calibracao = calibrar([0.98, 0.94, 0.82, 0.58], [0.69, 0.63, 0.61, 0.57, 0.43, 0.02], atual=0.80)

    assert calibracao.limiar == 0.75
    assert calibracao.regra == "mais_acertos"
    assert calibracao.lados == (0.69, 0.82)
    assert "9/10" in calibracao.motivo


def test_no_empate_entre_faixas_separadas_fica_a_mais_larga() -> None:
    calibracao = calibrar([0.45, 0.85, 0.90], [0.10, 0.20, 0.55], atual=0.50)

    assert calibracao.regra == "mais_acertos"
    assert calibracao.lados == (0.55, 0.85)
    assert calibracao.limiar == 0.70


def test_faixa_de_mais_acertos_pode_ir_ate_1() -> None:
    calibracao = calibrar([0.10, 0.20, 0.30], [0.90, 0.95, 0.96, 0.97], atual=0.50)

    assert calibracao.lados == (0.97, 1.0)
    assert calibracao.limiar == 0.98


def test_erro_critico_fica_entre_o_maior_erro_e_o_menor_acerto_acima_dele() -> None:
    calibracao = calibrar_erro_critico(
        erros=[0.76, 0.68, 0.60], acertos=[1.0, 0.98, 0.87, 0.86, 0.50, 0.30], atual=0.50
    )

    assert calibracao.limiar == 0.80
    assert calibracao.regra == "erro_critico"
    assert calibracao.lados == (0.76, 0.86)
    assert calibracao.folga == (0.04, 0.06)


def test_erro_critico_sem_acerto_acima_vai_ate_1() -> None:
    calibracao = calibrar_erro_critico(erros=[0.76, 0.68, 0.60], acertos=[0.50], atual=0.50)

    assert calibracao.lados == (0.76, 1.0)
    assert calibracao.limiar == 0.90


def test_erro_critico_com_menos_de_3_erros_nao_move_o_limiar() -> None:
    calibracao = calibrar_erro_critico(erros=[0.57], acertos=[0.9, 0.8, 0.7], atual=0.60)

    assert calibracao.limiar == 0.60
    assert calibracao.regra == "amostra_insuficiente"
    assert "1 erro crítico" in calibracao.motivo


def test_erro_critico_com_confianca_1_nao_tem_limiar_que_barre() -> None:
    calibracao = calibrar_erro_critico(erros=[1.0, 0.9, 0.8], acertos=[1.0], atual=0.50)

    assert calibracao.limiar == 0.50
    assert calibracao.regra == "erro_critico"
    assert calibracao.folga is None


@pytest.mark.parametrize(("limiar", "texto"), [(0.8, "0.80"), (0.705, "0.705"), (0.75, "0.75")])
def test_limiar_sai_com_duas_casas_ou_tres_quando_precisa(limiar: float, texto: str) -> None:
    assert formatar_limiar(limiar) == texto


def test_descricao_traz_limiar_regra_e_folga() -> None:
    texto = descrever(calibrar([0.94, 0.96, 0.98], [0.67, 0.13, 0.09], atual=0.90))

    assert texto.startswith("0.80 (ponto_medio, folga 0.13 abaixo e 0.14 acima")
    assert "atual 0.90" in texto
