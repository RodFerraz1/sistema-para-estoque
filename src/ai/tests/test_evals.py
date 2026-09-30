"""Rede de segurança dos rótulos em `evals/`: todo id citado existe no `corpus/` real e
todo produto citado existe no catálogo do seed."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.seed import PRODUTOS
from src.ai.corpus import ler_corpus
from src.ai.schemas import NENHUM_PRODUTO, Trecho

RAIZ = Path(__file__).resolve().parents[3]
EVALS = RAIZ / "evals"
INTENCOES = {"situacao_sku", "sugestao_compra", "politica_ou_fornecedor", "fora_de_escopo"}


def carregar(nome: str) -> list[dict]:
    return json.loads((EVALS / nome).read_text(encoding="utf-8"))


def test_todo_id_citado_nos_evals_existe_no_corpus() -> None:
    ids_corpus = {trecho.id for trecho in ler_corpus(RAIZ / "corpus")}
    citados = set()
    for caso in carregar("casos.json"):
        citados.update(caso["trechos_relevantes"])
        if caso["premissa_falsa"] is not None:
            citados.add(caso["premissa_falsa"])
    for par in carregar("pares_conflito.json"):
        citados.update((par["trecho_a"], par["trecho_b"]))

    assert citados - ids_corpus == set()


def test_todo_produto_aceito_nos_evals_existe_no_catalogo_do_seed() -> None:
    nomes = {produto.nome for produto in PRODUTOS} | {NENHUM_PRODUTO}

    for caso in carregar("casos.json"):
        assert caso["produtos_aceitos"], caso["id"]
        assert set(caso["produtos_aceitos"]) <= nomes, caso["id"]


def test_trechos_adversariais_tem_formato_de_trecho_e_nao_estao_no_corpus() -> None:
    ids_corpus = {trecho.id for trecho in ler_corpus(RAIZ / "corpus")}

    adversariais = [Trecho.model_validate(item) for item in carregar("trechos_adversariais.json")]

    assert len(adversariais) == 4
    assert {trecho.id for trecho in adversariais} & ids_corpus == set()


def test_casos_cobrem_intencoes_e_premissas_falsas() -> None:
    casos = carregar("casos.json")

    assert len(casos) == 20
    assert len({caso["id"] for caso in casos}) == 20
    por_intencao = Counter(caso["intencao"] for caso in casos)
    assert set(por_intencao) == INTENCOES
    assert min(por_intencao.values()) >= 4
    assert sum(caso["premissa_falsa"] is not None for caso in casos) >= 2
    for caso in casos:
        if caso["intencao"] == "fora_de_escopo":
            assert caso["trechos_relevantes"] == []
        if caso["premissa_falsa"] is not None:
            assert caso["premissa_falsa"] in caso["trechos_relevantes"]


def test_pares_de_conflito_tem_5_com_e_5_sem_conflito_entre_documentos_diferentes() -> None:
    pares = carregar("pares_conflito.json")

    assert Counter(par["conflitam"] for par in pares) == {True: 5, False: 5}
    for par in pares:
        assert par["trecho_a"].split("#")[0] != par["trecho_b"].split("#")[0]
