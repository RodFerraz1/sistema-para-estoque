"""Métricas da avaliação dos sinais, calculadas a partir das respostas gravadas."""
from __future__ import annotations

from scripts.avaliar_sinais import (
    LIMIARES,
    PontoVarredura,
    avaliacoes,
    escolher_limiar,
    relatorio,
    rodar,
    varrer_limiar,
)
from src.ai.in_memory import InMemoryDecisionModel
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
]
TRECHOS = {c["trecho_id"]: make_trecho(c["trecho_id"]) for c in CASOS}
DECISAO = InMemoryDecisionModel(
    sinais={
        "a.md#atraso-forte": {"atraso_do_fornecedor": 0.95},
        "a.md#atraso-fraco": {"atraso_do_fornecedor": 0.62},
        "b.md#cumpre": {"atraso_do_fornecedor": 0.41},
        "b.md#outro": {"atraso_do_fornecedor": 0.10, "encalhe": 0.88},
    },
    modelo="jev-1.13.0",
)


def resultado() -> dict:
    return {"respostas": rodar(DECISAO, CASOS, TRECHOS)}


def test_rodar_grava_uma_avaliacao_por_caso_com_o_trecho_do_caso() -> None:
    por_caso = avaliacoes(resultado())

    assert list(por_caso) == ["s01", "s02", "s03", "s04"]
    assert por_caso["s02"].trecho_id == "a.md#atraso-fraco"
    assert por_caso["s02"].atraso_do_fornecedor == 0.62


def test_varredura_conta_acertos_e_erros_com_o_limiar_estrito() -> None:
    varredura = varrer_limiar("atraso_do_fornecedor", CASOS, avaliacoes(resultado()))

    por_limiar = {p.limiar: p for p in varredura}
    assert [p.limiar for p in varredura] == list(LIMIARES)
    assert por_limiar[0.30] == PontoVarredura(0.30, acertos=3, falsos_positivos=1, falsos_negativos=0)
    assert por_limiar[0.45] == PontoVarredura(0.45, acertos=4, falsos_positivos=0, falsos_negativos=0)
    assert por_limiar[0.90] == PontoVarredura(0.90, acertos=3, falsos_positivos=0, falsos_negativos=1)


def test_limiar_e_o_de_mais_acertos_e_no_empate_o_mais_alto() -> None:
    varredura = varrer_limiar("atraso_do_fornecedor", CASOS, avaliacoes(resultado()))

    assert escolher_limiar(varredura) == 0.60


def test_relatorio_mostra_o_limiar_escolhido_de_cada_tipo() -> None:
    texto = relatorio(resultado(), CASOS)

    assert "Modelo: jev-1.13.0" in texto
    assert "atraso_do_fornecedor: 0.60" in texto
    assert "encalhe: 0.85" in texto
    assert "LIMIARES_SINAIS = LimiaresSinais(atraso_do_fornecedor=0.60, demanda_sazonal=0.90, encalhe=0.85)" in texto
