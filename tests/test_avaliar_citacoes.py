"""Métricas da avaliação das citações, calculadas a partir das respostas gravadas."""
from __future__ import annotations

from scripts.avaliar_citacoes import (
    LIMIARES,
    PontoVarredura,
    acertos_por_relacao,
    avaliacoes,
    escolher_limiar,
    relatorio,
    rodar,
    varrer_limiar,
)
from src.ai.in_memory import InMemoryDecisionModel
from tests.fakes import make_relacao, make_trecho


def caso(id: str, trecho_id: str, esperado: str) -> dict:
    return {"id": id, "afirmacao": f"Afirmação {id}.", "trecho_id": trecho_id, "esperado": esperado}


CASOS = [
    caso("v01", "a.md#sustenta-forte", "sustenta"),
    caso("c01", "a.md#contradiz", "contradiz"),
    caso("n01", "b.md#confirma-errado", "nao_trata"),
    caso("n02", "b.md#nao-trata", "nao_trata"),
]
TRECHOS = {c["trecho_id"]: make_trecho(c["trecho_id"]) for c in CASOS}


def decisao(confirma_errado: float = 0.72) -> InMemoryDecisionModel:
    return InMemoryDecisionModel(
        citacoes={
            "a.md#sustenta-forte": make_relacao("sustenta", 0.97),
            "a.md#contradiz": make_relacao("contradiz", 0.88),
            "b.md#confirma-errado": make_relacao("sustenta", confirma_errado),
            "b.md#nao-trata": make_relacao("nao_trata", 0.55),
        },
        modelo="jev-1.13.0",
    )


def resultado(confirma_errado: float = 0.72) -> dict:
    return {"respostas": rodar(decisao(confirma_errado), CASOS, TRECHOS)}


def test_rodar_grava_uma_avaliacao_por_caso_com_a_afirmacao_e_o_trecho_do_caso() -> None:
    por_caso = avaliacoes(resultado())

    assert list(por_caso) == ["v01", "c01", "n01", "n02"]
    assert (por_caso["c01"].afirmacao, por_caso["c01"].trecho_id) == ("Afirmação c01.", "a.md#contradiz")
    assert (por_caso["c01"].escolha, por_caso["c01"].confianca) == ("contradiz", 0.88)


def test_acerto_por_relacao_ignora_a_confianca() -> None:
    assert acertos_por_relacao(CASOS, avaliacoes(resultado())) == {
        "sustenta": (1, 1),
        "contradiz": (1, 1),
        "nao_trata": (1, 2),
    }


def test_varredura_conta_incertas_erros_e_confirmadas_erradas() -> None:
    varredura = varrer_limiar(CASOS, avaliacoes(resultado()))

    por_limiar = {p.limiar: p for p in varredura}
    assert [p.limiar for p in varredura] == list(LIMIARES)
    assert por_limiar[0.50] == PontoVarredura(0.50, incertas=0, erros=1, confirmadas_erradas=1)
    assert por_limiar[0.70] == PontoVarredura(0.70, incertas=1, erros=1, confirmadas_erradas=1)
    assert por_limiar[0.75] == PontoVarredura(0.75, incertas=2, erros=0, confirmadas_erradas=0)
    assert por_limiar[0.95] == PontoVarredura(0.95, incertas=3, erros=0, confirmadas_erradas=0)


def test_limiar_e_o_menor_sem_confirmada_errada() -> None:
    assert escolher_limiar(varrer_limiar(CASOS, avaliacoes(resultado()))) == 0.75


def test_sem_limiar_que_zere_as_confirmadas_erradas_fica_0_95() -> None:
    varredura = varrer_limiar(CASOS, avaliacoes(resultado(confirma_errado=0.99)))

    assert escolher_limiar(varredura) == 0.95


def test_relatorio_mostra_os_acertos_e_o_limiar_escolhido() -> None:
    texto = relatorio(resultado(), CASOS)

    assert "Modelo: jev-1.13.0" in texto
    assert "esperado nao_trata (1/2 acertos)" in texto
    assert "LIMIAR_CITACAO = 0.75" in texto
    assert "Nenhum limiar" not in texto
    assert "Nenhum limiar zera" in relatorio(resultado(confirma_errado=0.99), CASOS)
