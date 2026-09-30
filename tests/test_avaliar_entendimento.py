"""Métricas da avaliação do entendimento, calculadas a partir das respostas gravadas."""
from __future__ import annotations

from scripts.avaliar_entendimento import (
    LIMIAR_SEM_ZERO_ERROS,
    PontoVarredura,
    entendimentos,
    erros_de_intencao,
    erros_de_produto,
    escolher_limiar_produto,
    relatorio,
    rodar,
    varrer_limiar_produto,
)
from src.ai.in_memory import InMemoryDecisionModel
from tests.fakes import make_entendimento

CONFORTO = "Toalha Banho Conforto"
CASOS = [
    {"id": "c01", "pergunta": "toalha conforto?", "intencao": "situacao_sku", "produtos_aceitos": [CONFORTO]},
    {"id": "c02", "pergunta": "colcha nova?", "intencao": "sugestao_compra", "produtos_aceitos": ["nenhum"]},
    {"id": "c03", "pergunta": "katrina?", "intencao": "politica_ou_fornecedor", "produtos_aceitos": ["nenhum"]},
]
DECISAO = InMemoryDecisionModel(
    entendimentos={
        "toalha conforto?": make_entendimento("situacao_sku", 0.9, produto=CONFORTO, confianca_produto=0.92),
        "colcha nova?": make_entendimento("sugestao_compra", 0.8, produto="Colcha Bouti", confianca_produto=0.55),
        "katrina?": make_entendimento("sugestao_compra", 0.4, produto="nenhum", confianca_produto=0.99),
    }
)


def resultado() -> dict:
    return {"respostas": rodar(DECISAO, CASOS, [])}


def test_intencao_e_produto_contam_os_erros_por_caso() -> None:
    por_caso = entendimentos(resultado())

    assert [c["id"] for c, _ in erros_de_intencao(CASOS, por_caso)] == ["c03"]
    assert [c["id"] for c, _ in erros_de_produto(CASOS, por_caso)] == ["c02"]


def test_varredura_conta_so_os_produtos_usados_e_o_limiar_e_o_menor_sem_erro() -> None:
    varredura = varrer_limiar_produto(CASOS, entendimentos(resultado()))

    por_limiar = {p.limiar: (p.certos, p.errados) for p in varredura}
    assert por_limiar[0.30] == (1, 1)
    assert por_limiar[0.55] == (1, 1)
    assert por_limiar[0.60] == (1, 0)
    assert por_limiar[0.95] == (0, 0)
    assert escolher_limiar_produto(varredura) == 0.60


def test_sem_limiar_que_zere_os_erros_vale_o_padrao() -> None:
    varredura = [PontoVarredura(0.30, 3, 2), PontoVarredura(0.95, 1, 1)]

    assert escolher_limiar_produto(varredura) == LIMIAR_SEM_ZERO_ERROS


def test_relatorio_mostra_os_acertos_e_o_limiar() -> None:
    texto = relatorio(resultado(), CASOS)

    assert "Intenção: 2/3" in texto
    assert "Produto: 2/3" in texto
    assert "LIMIAR_PRODUTO = 0.60" in texto
