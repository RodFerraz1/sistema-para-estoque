"""Testes de `BuscaContexto` com `FakeEmbedder`, `InMemoryTrechosRepositorio` e `InMemoryDecisionModel`."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import pytest

from src.ai.busca import LIMIARES, BuscaContexto
from src.ai.decisao import DecisaoIndisponivel
from src.ai.in_memory import (
    FakeEmbedder,
    InMemoryDecisionModel,
    InMemoryTrechosRepositorio,
    Probabilidades,
)
from src.ai.schemas import Trecho, TrechoIndexado

PERGUNTA = "lead time da Katrina"


def trecho(id: str, texto: str = PERGUNTA) -> Trecho:
    return Trecho(
        id=id,
        documento=id.split("#")[0],
        titulo=f"Título de {id}",
        tipo="reuniao",
        data=date(2025, 3, 14),
        tags=["fornecedores"],
        texto=texto,
    )


def busca(trechos: list[Trecho], decisao: InMemoryDecisionModel) -> BuscaContexto:
    embedder = FakeEmbedder()
    repositorio = InMemoryTrechosRepositorio()
    por_documento: dict[str, list[TrechoIndexado]] = defaultdict(list)
    for t, vetor in zip(trechos, embedder.embed([t.texto for t in trechos]), strict=True):
        por_documento[t.documento].append(TrechoIndexado(**t.model_dump(), embedding=vetor))
    for documento, indexados in por_documento.items():
        repositorio.substituir_documento(documento, f"hash de {documento}", indexados)
    return BuscaContexto(embedder, repositorio, decisao)


def test_trecho_relevante_com_evidencia_e_aceito() -> None:
    decisao = InMemoryDecisionModel({"a.md#lead-time": {"relevante": 0.9, "tem_evidencia": 0.9}})

    [classificado] = busca([trecho("a.md#lead-time")], decisao).buscar(PERGUNTA).trechos

    assert classificado.id == "a.md#lead-time"
    assert classificado.classificacao == "aceito"
    assert classificado.motivo_descarte is None


def test_trecho_que_tenta_instruir_e_descartado_por_injecao() -> None:
    decisao = InMemoryDecisionModel(
        {"a.md#ata": {"relevante": 0.9, "tem_evidencia": 0.9, "tenta_instruir": 0.95}}
    )

    [classificado] = busca([trecho("a.md#ata")], decisao).buscar(PERGUNTA).trechos

    assert classificado.classificacao == "descartado"
    assert classificado.motivo_descarte == "injecao"


def test_trecho_que_contradiz_a_premissa_e_conflitante() -> None:
    decisao = InMemoryDecisionModel(
        {"a.md#revisao": {"relevante": 0.9, "tem_evidencia": 0.1, "contradiz_premissa": 0.95}}
    )

    [classificado] = busca([trecho("a.md#revisao")], decisao).buscar(PERGUNTA).trechos

    assert classificado.classificacao == "conflitante"
    assert classificado.motivo_descarte is None


def test_trecho_irrelevante_e_descartado_mesmo_com_evidencia() -> None:
    decisao = InMemoryDecisionModel({"a.md#malha-fina": {"relevante": 0.2, "tem_evidencia": 0.9}})

    [classificado] = busca([trecho("a.md#malha-fina")], decisao).buscar(PERGUNTA).trechos

    assert classificado.classificacao == "descartado"
    assert classificado.motivo_descarte == "irrelevante"


def test_trecho_relevante_sem_evidencia_e_descartado() -> None:
    decisao = InMemoryDecisionModel({"a.md#contexto": {"relevante": 0.9, "tem_evidencia": 0.05}})

    [classificado] = busca([trecho("a.md#contexto")], decisao).buscar(PERGUNTA).trechos

    assert classificado.classificacao == "descartado"
    assert classificado.motivo_descarte == "sem_evidencia"


def classificar(probabilidades: Probabilidades) -> tuple[str, str | None]:
    decisao = InMemoryDecisionModel({"a.md#s": probabilidades})
    [classificado] = busca([trecho("a.md#s")], decisao).buscar(PERGUNTA).trechos
    return classificado.classificacao, classificado.motivo_descarte


def test_injecao_vem_antes_da_contradicao_e_da_evidencia() -> None:
    assert classificar(
        {"tenta_instruir": 0.95, "contradiz_premissa": 0.95, "relevante": 0.9, "tem_evidencia": 0.9}
    ) == ("descartado", "injecao")


def test_contradicao_vem_antes_da_evidencia() -> None:
    assert classificar({"contradiz_premissa": 0.95, "relevante": 0.9, "tem_evidencia": 0.9}) == (
        "conflitante",
        None,
    )


def test_contradicao_vem_antes_da_relevancia() -> None:
    assert classificar({"contradiz_premissa": 0.95, "relevante": 0.1, "tem_evidencia": 0.9}) == (
        "conflitante",
        None,
    )


@pytest.mark.parametrize(
    ("probabilidades", "esperado"),
    [
        pytest.param(
            {"tenta_instruir": LIMIARES.injecao, "relevante": 0.9, "tem_evidencia": 0.9},
            ("aceito", None),
            id="injecao-no-limiar-nao-descarta",
        ),
        pytest.param(
            {"contradiz_premissa": LIMIARES.contradiz_premissa, "relevante": 0.9, "tem_evidencia": 0.9},
            ("aceito", None),
            id="contradicao-no-limiar-nao-e-conflitante",
        ),
        pytest.param(
            {"relevante": LIMIARES.relevante, "tem_evidencia": 0.9},
            ("aceito", None),
            id="relevancia-no-limiar-e-relevante",
        ),
        pytest.param(
            {"relevante": 0.9, "tem_evidencia": LIMIARES.evidencia},
            ("descartado", "sem_evidencia"),
            id="evidencia-no-limiar-nao-basta",
        ),
    ],
)
def test_valor_exatamente_no_limiar(
    probabilidades: Probabilidades, esperado: tuple[str, str | None]
) -> None:
    assert classificar(probabilidades) == esperado


def test_resultado_vem_por_classificacao_e_depois_por_similaridade() -> None:
    trechos = [
        trecho("a.md#1", "lead time da Katrina"),
        trecho("b.md#2", "lead time da Katrina em dias"),
        trecho("c.md#3", "lead time da Katrina em dias corridos"),
        trecho("d.md#4", "lead time da Katrina em dias corridos no contrato"),
    ]
    decisao = InMemoryDecisionModel(
        {
            "a.md#1": {"relevante": 0.1},
            "b.md#2": {"contradiz_premissa": 0.95},
            "c.md#3": {"relevante": 0.9, "tem_evidencia": 0.9},
            "d.md#4": {"relevante": 0.9, "tem_evidencia": 0.9},
        }
    )

    resultado = busca(trechos, decisao).buscar(PERGUNTA)

    assert [(t.id, t.classificacao) for t in resultado.trechos] == [
        ("c.md#3", "aceito"),
        ("d.md#4", "aceito"),
        ("b.md#2", "conflitante"),
        ("a.md#1", "descartado"),
    ]
    similaridades = [t.similaridade for t in resultado.trechos]
    assert similaridades[0] > similaridades[1]


def test_resultado_informa_o_modelo_que_avaliou_os_trechos() -> None:
    decisao = InMemoryDecisionModel(modelo="jev-1.13.0")

    resultado = busca([trecho("a.md#s")], decisao).buscar(PERGUNTA)

    assert resultado.modelo == "jev-1.13.0"
    assert resultado.trechos[0].avaliacao.modelo == "jev-1.13.0"


def test_jev_indisponivel_propaga_sem_resultado_parcial() -> None:
    decisao = InMemoryDecisionModel(falhar_trechos=True)

    with pytest.raises(DecisaoIndisponivel):
        busca([trecho("a.md#s")], decisao).buscar(PERGUNTA)


def test_corpus_vazio_devolve_listas_vazias_sem_chamar_o_jev() -> None:
    resultado = busca([], InMemoryDecisionModel(falhar_trechos=True)).buscar(PERGUNTA)

    assert resultado.pergunta == PERGUNTA
    assert resultado.modelo is None
    assert resultado.trechos == []
    assert resultado.conflitos == []


def test_busca_avalia_so_os_k_mais_parecidos() -> None:
    trechos = [
        trecho("a.md#1", "lead time da Katrina"),
        trecho("b.md#2", "lead time da Katrina em dias"),
        trecho("c.md#3", "prazo de pagamento da Verdela"),
    ]

    resultado = busca(trechos, InMemoryDecisionModel()).buscar(PERGUNTA, k=2)

    assert {t.id for t in resultado.trechos} == {"a.md#1", "b.md#2"}
