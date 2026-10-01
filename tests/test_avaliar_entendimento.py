"""Métricas da avaliação do entendimento, calculadas a partir das respostas gravadas."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.avaliar_entendimento import (
    calibrar_faixas,
    calibrar_produto,
    carregar_casos,
    entendimentos,
    erros_de_intencao,
    erros_de_produto,
    nome_do_resultado,
    relatorio,
    rodar,
    varrer_limiar_produto,
)
from src.ai.chat import FAIXAS
from src.ai.identificacao import LIMIAR_PRODUTO
from src.ai.in_memory import InMemoryDecisionModel
from tests.fakes import make_entendimento

CONFORTO = "Toalha Banho Conforto"
BOUTI = "Colcha Bouti"


def caso(id_: str, intencao: str, produtos_aceitos: list[str], pergunta: str | None = None) -> dict:
    return {"id": id_, "pergunta": pergunta or f"pergunta {id_}?", "intencao": intencao, "produtos_aceitos": produtos_aceitos}


CASOS = [
    caso("c01", "situacao_sku", [CONFORTO]),
    caso("c02", "sugestao_compra", ["nenhum"]),
    caso("c03", "politica_ou_fornecedor", ["nenhum"]),
]
INTENCOES = [caso("i01", "situacao_sku", [BOUTI]), caso("i02", "fora_de_escopo", ["nenhum"])]
DECISAO = InMemoryDecisionModel(
    entendimentos={
        "pergunta c01?": make_entendimento("situacao_sku", 0.9, produto=CONFORTO, confianca_produto=0.92),
        "pergunta c02?": make_entendimento("sugestao_compra", 0.8, produto=BOUTI, confianca_produto=0.55),
        "pergunta c03?": make_entendimento("sugestao_compra", 0.4, produto="nenhum", confianca_produto=0.99),
        "pergunta i01?": make_entendimento("situacao_sku", 0.97, produto=BOUTI, confianca_produto=0.7),
        "pergunta i02?": make_entendimento("fora_de_escopo", 1.0),
    }
)


def resultado(casos: list[dict]) -> dict:
    return {"respostas": rodar(DECISAO, casos, [])}


def entendidos(intencoes: list[tuple[str, bool, float]]) -> tuple[list[dict], dict]:
    """Casos `situacao_sku` e entendimentos de (id, intenção certa, confiança)."""
    casos = [caso(id_, "situacao_sku", ["nenhum"]) for id_, _, _ in intencoes]
    por_caso = {
        id_: make_entendimento("situacao_sku" if certa else "fora_de_escopo", confianca)
        for id_, certa, confianca in intencoes
    }
    return casos, por_caso


def como_resultado(por_caso: dict) -> dict:
    return {
        "respostas": [
            {"caso": id_, "latencia_s": 0.1, "entendimento": e.model_dump(mode="json")} for id_, e in por_caso.items()
        ]
    }


def test_intencao_e_produto_contam_os_erros_por_caso() -> None:
    por_caso = entendimentos(resultado(CASOS))

    assert [c["id"] for c, _ in erros_de_intencao(CASOS, por_caso)] == ["c03"]
    assert [c["id"] for c, _ in erros_de_produto(CASOS, por_caso)] == ["c02"]


def test_varredura_conta_so_os_produtos_usados() -> None:
    varredura = varrer_limiar_produto(CASOS, entendimentos(resultado(CASOS)))

    por_limiar = {p.limiar: (p.certos, p.errados) for p in varredura}
    assert por_limiar[0.30] == (1, 1)
    assert por_limiar[0.55] == (1, 1)
    assert por_limiar[0.60] == (1, 0)
    assert por_limiar[0.95] == (0, 0)


def test_produto_com_menos_de_3_erros_mantem_o_limiar() -> None:
    calibracao = calibrar_produto(CASOS, entendimentos(resultado(CASOS)))

    assert calibracao.regra == "amostra_insuficiente"
    assert calibracao.limiar == LIMIAR_PRODUTO


def test_produto_com_3_erros_usados_vai_para_o_meio_entre_o_maior_erro_e_o_acerto_acima() -> None:
    casos = [caso(f"e{n}", "situacao_sku", ["nenhum"]) for n in range(3)] + [
        caso(f"a{n}", "situacao_sku", [CONFORTO]) for n in range(2)
    ] + [caso("n0", "situacao_sku", [CONFORTO])]
    confiancas = {"e0": 0.50, "e1": 0.62, "e2": 0.66, "a0": 0.58, "a1": 0.84}
    por_caso = {id_: make_entendimento(produto=CONFORTO, confianca_produto=c) for id_, c in confiancas.items()}
    por_caso["n0"] = make_entendimento(produto="nenhum", confianca_produto=0.3)

    calibracao = calibrar_produto(casos, por_caso)

    assert calibracao.regra == "erro_critico"
    assert calibracao.lados == (0.66, 0.84)
    assert calibracao.limiar == 0.75


def test_faixas_com_pouco_erro_ficam_como_estao() -> None:
    faixas = calibrar_faixas(CASOS, entendimentos(resultado(CASOS)))

    assert faixas.media.regra == "amostra_insuficiente"
    assert faixas.media.limiar == FAIXAS.media
    assert faixas.alta.regra == "amostra_insuficiente"
    assert faixas.alta.limiar == FAIXAS.alta
    assert not faixas.em_conflito


def test_media_pela_regra_com_3_intencoes_erradas_contadas_uma_vez_por_pergunta() -> None:
    casos, por_caso = entendidos(
        [("a", True, 0.91), ("b", True, 0.81), ("c", True, 0.71), ("d", False, 0.45), ("e", False, 0.40), ("f", False, 0.30)]
    )
    repetido = {**casos[3], "id": "d2"}
    por_caso["d2"] = make_entendimento("fora_de_escopo", 0.75)

    faixas = calibrar_faixas([*casos, repetido], por_caso)

    assert faixas.media.regra == "ponto_medio"
    assert faixas.media.lados == (0.45, 0.71)
    assert faixas.media.limiar == 0.60
    assert not faixas.em_conflito


def test_alta_muda_com_3_erros_acima_da_alta_atual_e_o_conflito_com_a_media_mantem_as_faixas() -> None:
    casos, por_caso = entendidos(
        [("a", True, 0.91), ("b", True, 0.81), ("c", True, 0.71), ("d", False, 0.80), ("e", False, 0.82), ("f", False, 0.84)]
    )

    faixas = calibrar_faixas(casos, por_caso)
    texto = relatorio(como_resultado(por_caso), {"casos.json": casos})

    assert faixas.alta.regra == "erro_critico"
    assert faixas.alta.lados == (0.84, 0.91)
    assert faixas.alta.limiar == 0.90
    assert faixas.media.regra == "mais_acertos"
    assert faixas.em_conflito
    assert "media 0.90 >= alta 0.90: as faixas ficam (alta 0.80, media 0.50) e o dev decide" in texto


def test_alta_nao_conta_erro_abaixo_dela() -> None:
    casos, por_caso = entendidos(
        [("a", True, 0.95), ("b", True, 0.90), ("c", True, 0.85), ("d", False, 0.79), ("e", False, 0.60), ("f", False, 0.84)]
    )

    faixas = calibrar_faixas(casos, por_caso)

    assert faixas.alta.regra == "amostra_insuficiente"
    assert faixas.alta.limiar == FAIXAS.alta


def test_carregar_casos_por_arquivo_recusa_id_repetido(tmp_path: Path) -> None:
    casos = tmp_path / "casos.json"
    intencoes = tmp_path / "intencoes.json"
    casos.write_text(json.dumps(CASOS), encoding="utf-8")
    intencoes.write_text(json.dumps(INTENCOES), encoding="utf-8")
    repetido = tmp_path / "repetido.json"
    repetido.write_text(json.dumps([CASOS[0]]), encoding="utf-8")

    assert list(carregar_casos([casos, intencoes])) == ["casos.json", "intencoes.json"]
    with pytest.raises(ValueError, match="c01"):
        carregar_casos([casos, repetido])


def test_nome_do_resultado_leva_o_rotulo() -> None:
    assert nome_do_resultado(date(2026, 10, 1), "antes") == "entendimento-2026-10-01-antes.json"
    assert nome_do_resultado(date(2026, 10, 1), None) == "entendimento-2026-10-01.json"


def test_relatorio_mostra_o_acerto_por_arquivo_e_as_regras() -> None:
    texto = relatorio(resultado(CASOS + INTENCOES), {"casos.json": CASOS, "intencoes.json": INTENCOES})

    assert "Intenção (casos.json): 2/3" in texto
    assert "Intenção (intencoes.json): 2/2" in texto
    assert "Intenção (total): 4/5" in texto
    assert "Produto (casos.json): 2/3" in texto
    assert "Produto (total): 4/5" in texto
    assert "Regra de calibração do produto: 0.60 (amostra_insuficiente" in texto
    assert "LIMIAR_PRODUTO = 0.60" in texto
    assert "Regra de calibração de FAIXAS.media: 0.50 (amostra_insuficiente" in texto
    assert "FAIXAS = FaixasConfianca(alta=0.80, media=0.50)" in texto


def test_relatorio_de_um_arquivo_nao_repete_o_total() -> None:
    texto = relatorio(resultado(CASOS), {"casos.json": CASOS})

    assert "Intenção (casos.json): 2/3" in texto
    assert "(total)" not in texto
