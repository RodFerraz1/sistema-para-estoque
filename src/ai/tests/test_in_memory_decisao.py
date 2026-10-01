"""Testes do `InMemoryDecisionModel` no entendimento da pergunta, nos sinais e nas citações."""
from __future__ import annotations

import pytest

from src.ai.decisao import DecisaoIndisponivel
from src.ai.in_memory import InMemoryDecisionModel
from src.ai.schemas import ProdutoDoSinal
from tests.fakes import make_entendimento, make_relacao, make_trecho

TOALHA = ProdutoDoSinal(nome="Toalha Banho Conforto", categoria="felpudo")


def test_entendimento_configurado_por_pergunta_e_padrao_para_as_outras() -> None:
    da_toalha = make_entendimento("situacao_sku", produto="Toalha Banho Conforto")
    padrao = make_entendimento("politica_ou_fornecedor", 0.6)
    decisao = InMemoryDecisionModel(
        entendimentos={"como tá a toalha?": da_toalha}, entendimento_padrao=padrao
    )

    assert decisao.entender_pergunta("como tá a toalha?", []) == da_toalha
    assert decisao.entender_pergunta("e a Katrina?", []) == padrao


def test_sem_configuracao_a_pergunta_fica_fora_de_escopo_sem_produto() -> None:
    entendimento = InMemoryDecisionModel().entender_pergunta("qualquer coisa", [])

    assert (entendimento.intencao.escolha, entendimento.produto.escolha) == ("fora_de_escopo", "nenhum")


def test_falha_no_entendimento_como_o_jev_fora_do_ar() -> None:
    with pytest.raises(DecisaoIndisponivel):
        InMemoryDecisionModel(falhar_entendimento=True).entender_pergunta("como tá a toalha?", [])


def test_sinais_configurados_por_trecho_com_padrao_e_zero_no_resto() -> None:
    decisao = InMemoryDecisionModel(
        sinais={"a.md#atraso": {"atraso_do_fornecedor": 0.9}},
        sinais_padrao={"encalhe": 0.3},
        modelo="jev-1.13.0",
    )

    atraso, outro = decisao.avaliar_sinais(
        "Katrina Têxtil", TOALHA, [make_trecho("a.md#atraso"), make_trecho("b.md#outro")]
    )

    assert (atraso.trecho_id, atraso.probabilidades) == (
        "a.md#atraso",
        {"atraso_do_fornecedor": 0.9, "demanda_sazonal": 0.0, "encalhe": 0.3},
    )
    assert (outro.trecho_id, outro.probabilidades, outro.modelo) == (
        "b.md#outro",
        {"atraso_do_fornecedor": 0.0, "demanda_sazonal": 0.0, "encalhe": 0.3},
        "jev-1.13.0",
    )


def test_falha_nos_sinais_como_o_jev_fora_do_ar() -> None:
    with pytest.raises(DecisaoIndisponivel):
        InMemoryDecisionModel(falhar_sinais=True).avaliar_sinais("Katrina Têxtil", TOALHA, [make_trecho("a.md#s")])


def test_citacoes_configuradas_pelo_trecho_citado_e_padrao_nao_trata() -> None:
    decisao = InMemoryDecisionModel(citacoes={"a.md#atraso": make_relacao("sustenta", 0.9)}, modelo="jev-1.13.0")

    sustenta, padrao = decisao.verificar_citacoes(
        [("A Katrina atrasa.", make_trecho("a.md#atraso")), ("A Verdela atrasa.", make_trecho("b.md#outro"))]
    )

    assert (sustenta.afirmacao, sustenta.trecho_id, sustenta.escolha, sustenta.confianca, sustenta.modelo) == (
        "A Katrina atrasa.",
        "a.md#atraso",
        "sustenta",
        0.9,
        "jev-1.13.0",
    )
    assert (padrao.trecho_id, padrao.escolha, padrao.confianca) == ("b.md#outro", "nao_trata", 1.0)


def test_falha_nas_citacoes_como_o_jev_fora_do_ar() -> None:
    with pytest.raises(DecisaoIndisponivel):
        InMemoryDecisionModel(falhar_citacoes=True).verificar_citacoes([("A Katrina atrasa.", make_trecho("a.md#s"))])
