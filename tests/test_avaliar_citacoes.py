"""Métricas da avaliação das citações, calculadas a partir das respostas gravadas."""
from __future__ import annotations

from scripts.avaliar_citacoes import (
    LIMIARES,
    PontoVarredura,
    acertos_por_relacao,
    avaliacoes,
    calibrar_limiar,
    relatorio,
    rodar,
    varrer_limiar,
)
from src.ai.citacoes import LIMIAR_CITACAO
from src.ai.in_memory import InMemoryDecisionModel
from tests.fakes import make_relacao, make_trecho


def caso(id: str, trecho_id: str, esperado: str) -> dict:
    return {"id": id, "afirmacao": f"Afirmação {id}.", "trecho_id": trecho_id, "esperado": esperado}


CASOS = [
    caso("v01", "a.md#sustenta-forte", "sustenta"),
    caso("c01", "a.md#contradiz", "contradiz"),
    caso("n01", "b.md#confirma-errado", "nao_trata"),
    caso("n02", "b.md#nao-trata", "nao_trata"),
    caso("n03", "c.md#outro-fornecedor", "nao_trata"),
    caso("n04", "d.md#outro-fornecedor", "nao_trata"),
]
TRECHOS = {c["trecho_id"]: make_trecho(c["trecho_id"]) for c in CASOS}
DECISAO = InMemoryDecisionModel(
    citacoes={
        "a.md#sustenta-forte": make_relacao("sustenta", 0.97),
        "a.md#contradiz": make_relacao("contradiz", 0.88),
        "b.md#confirma-errado": make_relacao("sustenta", 0.72),
        "b.md#nao-trata": make_relacao("nao_trata", 0.55),
        "c.md#outro-fornecedor": make_relacao("contradiz", 0.65),
        "d.md#outro-fornecedor": make_relacao("contradiz", 0.60),
    },
    modelo="jev-1.13.0",
)


def resultado() -> dict:
    return {"respostas": rodar(DECISAO, CASOS, TRECHOS)}


def test_rodar_grava_uma_avaliacao_por_caso_com_a_afirmacao_e_o_trecho_do_caso() -> None:
    por_caso = avaliacoes(resultado())

    assert list(por_caso) == ["v01", "c01", "n01", "n02", "n03", "n04"]
    assert (por_caso["c01"].afirmacao, por_caso["c01"].trecho_id) == ("Afirmação c01.", "a.md#contradiz")
    assert (por_caso["c01"].escolha, por_caso["c01"].confianca) == ("contradiz", 0.88)


def test_acerto_por_relacao_ignora_a_confianca() -> None:
    assert acertos_por_relacao(CASOS, avaliacoes(resultado())) == {
        "sustenta": (1, 1),
        "contradiz": (1, 1),
        "nao_trata": (1, 4),
    }


def test_varredura_conta_incertas_erros_e_confirmadas_erradas() -> None:
    varredura = varrer_limiar(CASOS, avaliacoes(resultado()))

    por_limiar = {p.limiar: p for p in varredura}
    assert [p.limiar for p in varredura] == list(LIMIARES)
    assert por_limiar[0.50] == PontoVarredura(0.50, incertas=0, erros=3, confirmadas_erradas=1)
    assert por_limiar[0.70] == PontoVarredura(0.70, incertas=3, erros=1, confirmadas_erradas=1)
    assert por_limiar[0.75] == PontoVarredura(0.75, incertas=4, erros=0, confirmadas_erradas=0)
    assert por_limiar[0.95] == PontoVarredura(0.95, incertas=5, erros=0, confirmadas_erradas=0)


def test_qualquer_veredito_errado_e_erro_critico_e_o_limiar_fica_acima_do_maior() -> None:
    calibracao = calibrar_limiar(CASOS, avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (0.80, "erro_critico")
    assert calibracao.lados == (0.72, 0.88)


def test_com_menos_de_3_vereditos_errados_o_limiar_atual_fica() -> None:
    calibracao = calibrar_limiar(CASOS[:4], avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (LIMIAR_CITACAO, "amostra_insuficiente")


def test_relatorio_mostra_os_acertos_a_regra_e_o_limiar() -> None:
    texto = relatorio(resultado(), CASOS)

    assert "Modelo: jev-1.13.0" in texto
    assert "esperado nao_trata (1/4 acertos)" in texto
    assert "Regra de calibração: 0.80 (erro_critico, folga 0.08 abaixo e 0.08 acima" in texto
    assert "LIMIAR_CITACAO = 0.80" in texto
