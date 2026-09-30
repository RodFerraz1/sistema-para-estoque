"""Testes do `InMemoryDecisionModel` no entendimento da pergunta."""
from __future__ import annotations

import pytest

from src.ai.decisao import DecisaoIndisponivel
from src.ai.in_memory import InMemoryDecisionModel
from tests.fakes import make_entendimento


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
