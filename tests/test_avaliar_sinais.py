"""Métricas da avaliação dos sinais, calculadas a partir das respostas gravadas."""
from __future__ import annotations

from scripts.avaliar_sinais import (
    LIMIARES,
    PontoVarredura,
    avaliacoes,
    calibrar_tipo,
    relatorio,
    rodar,
    varrer_limiar,
)
from src.ai.in_memory import InMemoryDecisionModel
from src.ai.sinais import LIMIARES_SINAIS
from tests.fakes import make_trecho

TOALHA = {"nome": "Toalha Banho Conforto", "categoria": "felpudo"}


def caso(id: str, trecho_id: str, atraso: bool, encalhe: bool = False) -> dict:
    return {
        "id": id,
        "fornecedor": "Katrina Têxtil",
        "produto": TOALHA,
        "trecho_id": trecho_id,
        "esperado": {"atraso_do_fornecedor": atraso, "demanda_sazonal": False, "encalhe": encalhe},
    }


CASOS = [
    caso("s01", "a.md#atraso-forte", True),
    caso("s02", "a.md#atraso-fraco", True),
    caso("s03", "b.md#cumpre", False),
    caso("s04", "b.md#outro", False, encalhe=True),
    caso("s05", "a.md#atraso-medio", True),
    caso("s06", "c.md#prazo", False),
]
TRECHOS = {c["trecho_id"]: make_trecho(c["trecho_id"]) for c in CASOS}
DECISAO = InMemoryDecisionModel(
    sinais={
        "a.md#atraso-forte": {"atraso_do_fornecedor": 0.95},
        "a.md#atraso-fraco": {"atraso_do_fornecedor": 0.62},
        "b.md#cumpre": {"atraso_do_fornecedor": 0.41},
        "b.md#outro": {"atraso_do_fornecedor": 0.10, "encalhe": 0.88},
        "a.md#atraso-medio": {"atraso_do_fornecedor": 0.85},
        "c.md#prazo": {"atraso_do_fornecedor": 0.30},
    },
    modelo="jev-1.13.0",
)


def resultado() -> dict:
    return {"respostas": rodar(DECISAO, CASOS, TRECHOS)}


def test_rodar_grava_uma_avaliacao_por_caso_com_o_trecho_do_caso() -> None:
    por_caso = avaliacoes(resultado())

    assert list(por_caso) == ["s01", "s02", "s03", "s04", "s05", "s06"]
    assert por_caso["s02"].trecho_id == "a.md#atraso-fraco"
    assert por_caso["s02"].probabilidades["atraso_do_fornecedor"] == 0.62


def test_varredura_conta_acertos_e_erros_com_o_limiar_estrito() -> None:
    varredura = varrer_limiar("atraso_do_fornecedor", CASOS, avaliacoes(resultado()))

    por_limiar = {p.limiar: p for p in varredura}
    assert [p.limiar for p in varredura] == list(LIMIARES)
    assert por_limiar[0.30] == PontoVarredura(0.30, acertos=5, falsos_positivos=1, falsos_negativos=0)
    assert por_limiar[0.45] == PontoVarredura(0.45, acertos=6, falsos_positivos=0, falsos_negativos=0)
    assert por_limiar[0.90] == PontoVarredura(0.90, acertos=4, falsos_positivos=0, falsos_negativos=2)


def test_tipo_separavel_fica_no_ponto_medio_com_a_folga() -> None:
    calibracao = calibrar_tipo("atraso_do_fornecedor", CASOS, avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (0.50, "ponto_medio")
    assert calibracao.folga == (0.09, 0.12)
    assert calibracao.atual == LIMIARES_SINAIS["atraso_do_fornecedor"]


def test_tipo_com_menos_de_3_positivos_mantem_o_limiar_atual() -> None:
    calibracao = calibrar_tipo("encalhe", CASOS, avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (LIMIARES_SINAIS["encalhe"], "amostra_insuficiente")


def test_relatorio_mostra_limiar_regra_e_folga_de_cada_tipo() -> None:
    texto = relatorio(resultado(), CASOS)
    sazonal, encalhe = LIMIARES_SINAIS["demanda_sazonal"], LIMIARES_SINAIS["encalhe"]

    assert "Modelo: jev-1.13.0" in texto
    assert "atraso_do_fornecedor: 0.50 (ponto_medio, folga 0.09 abaixo e 0.12 acima" in texto
    assert f"encalhe: {encalhe:.2f} (amostra_insuficiente; 1 positivo e 5 negativos" in texto
    assert (
        f'LIMIARES_SINAIS = {{"atraso_do_fornecedor": 0.50, "demanda_sazonal": {sazonal:.2f}, "encalhe": {encalhe:.2f}}}'
        in texto
    )
