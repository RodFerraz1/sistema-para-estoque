"""Coleta dos pares das buscas e métricas da avaliação do conflito, sem rede."""
from __future__ import annotations

from datetime import date

from scripts.avaliar_conflitos import (
    LIMIARES,
    PontoVarredura,
    avaliacoes,
    calibrar_conflito,
    conflitos_por_pergunta,
    juntar,
    nome_do_resultado,
    pares_acima,
    pares_para_rotular,
    relatorio,
    rodar,
    texto_para_rotular,
    varrer_limiar,
)
from src.ai.busca import LIMIARES as LIMIARES_BUSCA
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel
from tests.fakes import make_trecho, repositorio_com


def par(a: str, b: str, conflitam: bool) -> dict:
    return {"trecho_a": a, "trecho_b": b, "conflitam": conflitam, "motivo": "Motivo."}


PARES = [
    par("contrato.md#prazos", "revisao.md#katrina", True),
    par("contrato.md#notas", "ata.md#natal", True),
    par("ficha.md#linhas", "ata.md#natal", True),
    par("contrato.md#volumes", "revisao.md#katrina", False),
    par("ficha.md#riscos", "revisao.md#malha", False),
    par("politica.md#r3", "ata.md#veraneio", False),
]
PROBABILIDADES = {
    ("contrato.md#prazos", "revisao.md#katrina"): 0.62,
    ("contrato.md#notas", "ata.md#natal"): 0.41,
    ("ficha.md#linhas", "ata.md#natal"): 0.30,
    ("contrato.md#volumes", "revisao.md#katrina"): 0.12,
    ("ficha.md#riscos", "revisao.md#malha"): 0.08,
    ("politica.md#r3", "ata.md#veraneio"): 0.02,
}
TRECHOS = {id: make_trecho(id, f"Texto de {id}.") for p in PARES for id in (p["trecho_a"], p["trecho_b"])}


def resultado(probabilidades: dict = PROBABILIDADES) -> dict:
    decisao = InMemoryDecisionModel(conflitos=probabilidades, modelo="jev-1.13.0")
    return {"respostas": rodar(decisao, PARES, TRECHOS)}


def busca(caso: str, *pares: tuple[str, str, float]) -> dict:
    return {
        "caso": caso,
        "pergunta": f"Pergunta {caso}",
        "pares": [{"trecho_a": a, "trecho_b": b, "conflitam": p, "modelo": "jev-1.13.0"} for a, b, p in pares],
    }


BUSCAS = [
    busca("c09", ("a.md#s", "b.md#s", 0.62), ("a.md#s", "c.md#s", 0.11), ("b.md#s", "c.md#s", 0.04)),
    busca("c11", ("b.md#s", "a.md#s", 0.58), ("c.md#s", "d.md#s", 0.35)),
    busca("c12"),
]


def test_juntar_grava_todo_par_avaliado_nas_buscas_das_perguntas_que_vao_ao_corpus() -> None:
    embedder = FakeEmbedder()
    trechos = [
        make_trecho("contrato.md#prazos", "lead time da Katrina"),
        make_trecho("revisao.md#katrina", "lead time da Katrina em dias"),
    ]
    decisao = InMemoryDecisionModel(
        padrao={"relevante": 0.9, "tem_evidencia": 0.9},
        conflitos={("contrato.md#prazos", "revisao.md#katrina"): 0.04},
        modelo="jev-1.13.0",
    )
    casos = [
        {"id": "c01", "pergunta": "estoque da toalha", "intencao": "situacao_sku"},
        {"id": "c09", "pergunta": "lead time da Katrina", "intencao": "sugestao_compra"},
        {"id": "c11", "pergunta": "lead time da Katrina?", "intencao": "politica_ou_fornecedor"},
        {"id": "c16", "pergunta": "chuva", "intencao": "fora_de_escopo"},
    ]

    buscas = juntar(embedder, repositorio_com(trechos, embedder), decisao, casos)

    assert [b["caso"] for b in buscas] == ["c09", "c11"]
    assert buscas[0]["pergunta"] == "lead time da Katrina"
    assert buscas[0]["pares"] == [
        {"trecho_a": "contrato.md#prazos", "trecho_b": "revisao.md#katrina", "conflitam": 0.04, "modelo": "jev-1.13.0"}
    ]


def test_pares_acima_do_limiar_saem_uma_vez_em_qualquer_ordem() -> None:
    assert pares_acima(BUSCAS, 0.10) == [("a.md#s", "b.md#s"), ("a.md#s", "c.md#s"), ("c.md#s", "d.md#s")]


def test_pares_para_rotular_deixam_de_fora_os_ja_rotulados_em_qualquer_ordem() -> None:
    rotulados = [par("c.md#s", "a.md#s", False)]

    assert pares_para_rotular(BUSCAS, rotulados, 0.10) == [("a.md#s", "b.md#s"), ("c.md#s", "d.md#s")]


def test_conflitos_por_pergunta_contam_os_pares_que_passam_do_limiar() -> None:
    assert conflitos_por_pergunta(BUSCAS, 0.10) == {"c09": 2, "c11": 2, "c12": 0}
    assert conflitos_por_pergunta(BUSCAS, 0.50) == {"c09": 1, "c11": 1, "c12": 0}


def test_texto_para_rotular_traz_o_texto_dos_dois_trechos_sem_a_probabilidade() -> None:
    texto = texto_para_rotular([("contrato.md#prazos", "revisao.md#katrina")], TRECHOS)

    assert "## Par 1" in texto
    assert "### contrato.md#prazos (reuniao, 2025-03-14)" in texto
    assert "Texto de revisao.md#katrina." in texto
    assert "0." not in texto


def test_nome_do_resultado_leva_a_data_e_o_rotulo() -> None:
    assert nome_do_resultado(date(2026, 10, 1), "antes") == "conflitos-2026-10-01-antes.json"
    assert nome_do_resultado(date(2026, 10, 1), None) == "conflitos-2026-10-01.json"
    assert nome_do_resultado(date(2026, 10, 1), "depois", prefixo="buscas-conflito") == (
        "buscas-conflito-2026-10-01-depois.json"
    )


def test_rodar_grava_uma_avaliacao_por_par_na_ordem_do_par() -> None:
    por_par = avaliacoes(resultado())

    assert list(por_par) == [(p["trecho_a"], p["trecho_b"]) for p in PARES]
    assert por_par[("contrato.md#notas", "ata.md#natal")].conflitam == 0.41


def test_varredura_conta_acertos_e_erros_com_o_limiar_estrito() -> None:
    varredura = varrer_limiar(PARES, avaliacoes(resultado()))

    por_limiar = {p.limiar: p for p in varredura}
    assert [p.limiar for p in varredura] == list(LIMIARES)
    assert (LIMIARES[0], LIMIARES[-1]) == (0.05, 0.90)
    assert por_limiar[0.05] == PontoVarredura(0.05, acertos=4, falsos_positivos=2, falsos_negativos=0)
    assert por_limiar[0.20] == PontoVarredura(0.20, acertos=6, falsos_positivos=0, falsos_negativos=0)
    assert por_limiar[0.50] == PontoVarredura(0.50, acertos=4, falsos_positivos=0, falsos_negativos=2)


def test_pares_separaveis_ficam_no_ponto_medio_com_a_folga() -> None:
    calibracao = calibrar_conflito(PARES, avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (0.20, "ponto_medio")
    assert calibracao.folga == (0.08, 0.10)
    assert calibracao.atual == LIMIARES_BUSCA.conflito


def test_pares_nao_separaveis_ficam_no_meio_da_faixa_de_mais_acertos() -> None:
    probabilidades = {**PROBABILIDADES, ("contrato.md#volumes", "revisao.md#katrina"): 0.45}

    calibracao = calibrar_conflito(PARES, avaliacoes(resultado(probabilidades)))

    assert (calibracao.limiar, calibracao.regra) == (0.20, "mais_acertos")
    assert calibracao.lados == (0.08, 0.30)


def test_menos_de_3_pares_com_conflito_mantem_o_limiar_atual() -> None:
    pares = [p for p in PARES if p["trecho_a"] != "ficha.md#linhas"]

    calibracao = calibrar_conflito(pares, avaliacoes(resultado()))

    assert (calibracao.limiar, calibracao.regra) == (LIMIARES_BUSCA.conflito, "amostra_insuficiente")


def test_relatorio_mostra_limiar_regra_folga_e_os_conflitos_por_busca() -> None:
    texto = relatorio(resultado(), PARES, BUSCAS)
    atual = f"{LIMIARES_BUSCA.conflito:.2f}"

    assert "Modelo: jev-1.13.0" in texto
    assert "## Pares (3 com conflito e 3 sem)" in texto
    assert "0.62  conflitam sim  contrato.md#prazos x revisao.md#katrina" in texto
    assert f"Regra de calibração: 0.20 (ponto_medio, folga 0.08 abaixo e 0.10 acima; separável entre 0.12 e 0.30; atual {atual})" in texto
    assert "LIMIARES.conflito = 0.20" in texto
    assert f"## Conflitos por busca (limiar atual {atual} e calibrado 0.20)" in texto
    assert "c11   2 pares" in texto
    assert "total: " in texto


def test_relatorio_sem_buscas_nao_conta_conflitos_por_busca() -> None:
    assert "Conflitos por busca" not in relatorio(resultado(), PARES)
