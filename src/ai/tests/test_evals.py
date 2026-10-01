"""Rede de segurança dos rótulos em `evals/`: todo id citado existe no `corpus/` real e
todo produto e fornecedor citados existem no seed."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from scripts.relatorio_registros import normalizar_pergunta
from scripts.seed import FORNECEDORES, PRODUTOS
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
    citados.update(caso["trecho_id"] for caso in carregar("sinais.json"))
    citados.update(caso["trecho_id"] for caso in carregar("citacoes.json"))

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


def test_pares_de_conflito_tem_ao_menos_5_de_cada_rotulo_entre_documentos_diferentes() -> None:
    pares = carregar("pares_conflito.json")

    assert min(Counter(par["conflitam"] for par in pares).values()) >= 5
    assert set(Counter(par["conflitam"] for par in pares)) == {True, False}
    assert len({frozenset((par["trecho_a"], par["trecho_b"])) for par in pares}) == len(pares)
    for par in pares:
        assert par["motivo"], par
        assert par["trecho_a"].split("#")[0] != par["trecho_b"].split("#")[0], par


def test_casos_de_sinais_citam_produto_e_fornecedor_do_seed_com_os_tres_rotulos() -> None:
    casos = carregar("sinais.json")
    produtos = {(produto.nome, produto.categoria) for produto in PRODUTOS}
    fornecedores = {fornecedor.nome for fornecedor in FORNECEDORES}

    assert len(casos) >= 15
    assert len({caso["id"] for caso in casos}) == len(casos)
    for caso in casos:
        assert (caso["produto"]["nome"], caso["produto"]["categoria"]) in produtos, caso["id"]
        assert caso["fornecedor"] in fornecedores, caso["id"]
        assert set(caso["esperado"]) == {"atraso_do_fornecedor", "demanda_sazonal", "encalhe"}, caso["id"]
    for tipo in ("atraso_do_fornecedor", "demanda_sazonal", "encalhe"):
        assert sum(caso["esperado"][tipo] for caso in casos) >= 3, tipo


def test_pares_de_citacao_tem_ao_menos_5_de_cada_relacao() -> None:
    casos = carregar("citacoes.json")

    assert len(casos) >= 15
    assert len({caso["id"] for caso in casos}) == len(casos)
    assert all(caso["afirmacao"] and caso["motivo"] for caso in casos)
    por_relacao = Counter(caso["esperado"] for caso in casos)
    assert set(por_relacao) == {"sustenta", "contradiz", "nao_trata"}
    assert min(por_relacao.values()) >= 5


def test_casos_do_redator_tem_o_formato_dos_casos_sem_repetir_pergunta() -> None:
    casos = carregar("casos_redator.json")
    perguntas_dos_casos = {caso["pergunta"] for caso in carregar("casos.json")}

    assert len({caso["id"] for caso in casos}) == len(casos) == 4
    for caso in casos:
        assert set(caso) == {"id", "pergunta", "intencao"}, caso["id"]
        assert caso["intencao"] in INTENCOES, caso["id"]
        assert caso["pergunta"] not in perguntas_dos_casos, caso["id"]


def test_intencoes_tem_as_quatro_intencoes_sem_repetir_casos_e_com_produtos_do_seed() -> None:
    casos = carregar("intencoes.json")
    perguntas_dos_casos = {normalizar_pergunta(caso["pergunta"]) for caso in carregar("casos.json")}
    nomes = {produto.nome for produto in PRODUTOS} | {NENHUM_PRODUTO}

    assert len(casos) >= 12
    assert len({caso["id"] for caso in casos}) == len(casos)
    assert len({normalizar_pergunta(caso["pergunta"]) for caso in casos}) == len(casos)
    assert {caso["id"] for caso in casos} & {caso["id"] for caso in carregar("casos.json")} == set()
    por_intencao = Counter(caso["intencao"] for caso in casos)
    assert set(por_intencao) == INTENCOES
    assert min(por_intencao.values()) >= 3
    for caso in casos:
        assert set(caso) == {"id", "pergunta", "intencao", "produtos_aceitos"}, caso["id"]
        assert normalizar_pergunta(caso["pergunta"]) not in perguntas_dos_casos, caso["id"]
        assert caso["produtos_aceitos"], caso["id"]
        assert set(caso["produtos_aceitos"]) <= nomes, caso["id"]
