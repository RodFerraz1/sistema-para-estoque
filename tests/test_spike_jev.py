"""Métricas do spike do Jev, calculadas a partir das respostas cruas gravadas."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx2
import pytest
from typesafe_sdk import SystemOneResponse, TypeSafeRateLimitError
from typesafe_sdk._core.schemas.base import parse_response

from scripts.spike_jev import (
    avaliar_conflito,
    avaliar_injecao,
    avaliar_intencao,
    escolher_limiar_relevancia,
    gravar,
    percentil,
    relatorio,
    rodar,
    tokens_por_busca,
    varrer_relevancia,
)
from src.ai.schemas import Trecho


def caso(id: str, intencao: str = "situacao_sku", relevantes: list[str] | None = None) -> dict:
    return {
        "id": id,
        "pergunta": f"pergunta {id}",
        "intencao": intencao,
        "trechos_relevantes": relevantes or [],
        "premissa_falsa": None,
    }


def intencao(caso: str, escolha: str, confianca: float) -> dict:
    return {"caso": caso, "escolha": escolha, "confianca": confianca}


def relevancia(
    caso: str,
    trecho: str,
    relevante: float = 0.0,
    tem_evidencia: float = 0.0,
    tenta_instruir: float = 0.0,
    input_tokens: int = 0,
) -> dict:
    return {
        "caso": caso,
        "trecho": trecho,
        "respostas": {
            "relevante": relevante,
            "tem_evidencia": tem_evidencia,
            "contradiz_premissa": 0.0,
            "tenta_instruir": tenta_instruir,
        },
        "input_tokens": input_tokens,
    }


def par(a: str, b: str, conflitam: bool) -> dict:
    return {"trecho_a": a, "trecho_b": b, "conflitam": conflitam, "motivo": ""}


def conflito(a: str, b: str, probabilidade: float, input_tokens: int = 0) -> dict:
    return {"trecho_a": a, "trecho_b": b, "conflitam": probabilidade, "input_tokens": input_tokens}


class TestIntencao:
    def test_passa_com_17_acertos_e_erros_sem_confianca_alta(self) -> None:
        casos = [caso(f"c{i}") for i in range(20)]
        registros = [intencao(f"c{i}", "situacao_sku", 0.9) for i in range(17)]
        registros += [intencao(f"c{i}", "fora_de_escopo", 0.79) for i in range(17, 20)]

        avaliacao = avaliar_intencao(registros, casos)

        assert (avaliacao.acertos, avaliacao.total) == (17, 20)
        assert [erro["caso"] for erro in avaliacao.erros] == ["c17", "c18", "c19"]
        assert avaliacao.passa

    def test_nao_passa_com_16_acertos(self) -> None:
        casos = [caso(f"c{i}") for i in range(20)]
        registros = [intencao(f"c{i}", "situacao_sku", 0.9) for i in range(16)]
        registros += [intencao(f"c{i}", "fora_de_escopo", 0.5) for i in range(16, 20)]

        assert not avaliar_intencao(registros, casos).passa

    def test_nao_passa_com_um_erro_confiante(self) -> None:
        casos = [caso(f"c{i}") for i in range(20)]
        registros = [intencao(f"c{i}", "situacao_sku", 0.9) for i in range(19)]
        registros.append(intencao("c19", "fora_de_escopo", 0.8))

        assert not avaliar_intencao(registros, casos).passa


class TestRelevancia:
    def test_aceito_exige_relevante_no_limiar_e_evidencia_acima_dele(self) -> None:
        casos = [caso("c1", relevantes=["a", "b"])]
        registros = [
            relevancia("c1", "a", relevante=0.5, tem_evidencia=0.9),
            relevancia("c1", "b", relevante=0.9, tem_evidencia=0.5),
            relevancia("c1", "x", relevante=0.9, tem_evidencia=0.9),
        ]

        pontos = {(p.relevante, p.evidencia): p for p in varrer_relevancia(registros, casos, set())}

        ponto = pontos[(0.5, 0.45)]
        assert (ponto.verdadeiros_positivos, ponto.falsos_positivos) == (2, 1)
        assert ponto.recall == 1.0
        assert ponto.precisao == pytest.approx(2 / 3)
        assert pontos[(0.55, 0.5)].recall == 0.0

    def test_trechos_adversariais_ficam_fora_da_varredura(self) -> None:
        casos = [caso("c1", relevantes=["a"])]
        registros = [
            relevancia("c1", "a", relevante=0.9, tem_evidencia=0.9),
            relevancia("c1", "adv", relevante=0.9, tem_evidencia=0.9),
        ]

        [ponto, *_] = varrer_relevancia(registros, casos, {"adv"})

        assert ponto.precisao == 1.0

    def test_escolhe_maior_recall_com_precisao_minima(self) -> None:
        casos = [caso("c1", relevantes=["a", "b"])]
        registros = [
            relevancia("c1", "a", relevante=0.9, tem_evidencia=0.9),
            relevancia("c1", "b", relevante=0.9, tem_evidencia=0.3),
            relevancia("c1", "x", relevante=0.9, tem_evidencia=0.2),
            relevancia("c1", "y", relevante=0.1, tem_evidencia=0.9),
        ]

        escolhido = escolher_limiar_relevancia(varrer_relevancia(registros, casos, set()))

        assert escolhido is not None
        assert (escolhido.recall, escolhido.precisao) == (1.0, 1.0)
        assert 0.2 <= escolhido.evidencia < 0.3
        assert 0.1 < escolhido.relevante <= 0.9

    def test_sem_ponto_com_precisao_minima_nao_escolhe(self) -> None:
        casos = [caso("c1", relevantes=["a"])]
        registros = [relevancia("c1", "a")] + [
            relevancia("c1", f"x{i}", relevante=0.9, tem_evidencia=0.9) for i in range(3)
        ]

        assert escolher_limiar_relevancia(varrer_relevancia(registros, casos, set())) is None


class TestInjecao:
    def test_adversarial_conta_pelo_pior_par_e_corpus_pelo_pior_par(self) -> None:
        registros = [
            relevancia("c1", "adv", tenta_instruir=0.9),
            relevancia("c2", "adv", tenta_instruir=0.6),
            relevancia("c1", "a", tenta_instruir=0.1),
            relevancia("c2", "a", tenta_instruir=0.7),
            relevancia("c1", "b", tenta_instruir=0.2),
        ]

        avaliacao = avaliar_injecao(registros, {"adv"})

        assert avaliacao.minimo_adversarial == {"adv": 0.6}
        assert avaliacao.maximo_corpus == {"a": 0.7, "b": 0.2}
        assert avaliacao.faixa == [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55]
        assert avaliacao.limiar == pytest.approx(0.35)
        assert avaliacao.passa

    def test_nao_passa_quando_nenhum_limiar_separa(self) -> None:
        registros = [
            relevancia("c1", "adv", tenta_instruir=0.3),
            relevancia("c1", "a", tenta_instruir=0.8),
            relevancia("c1", "b", tenta_instruir=0.8),
        ]

        avaliacao = avaliar_injecao(registros, {"adv"})

        assert avaliacao.faixa == []
        assert avaliacao.limiar is None
        assert not avaliacao.passa


class TestConflito:
    def test_separa_quando_todo_par_com_conflito_supera_todo_par_sem(self) -> None:
        pares = [par("a", "b", True), par("c", "d", True), par("a", "c", False), par("b", "d", False)]
        registros = [conflito("a", "b", 0.8), conflito("c", "d", 0.6), conflito("a", "c", 0.4), conflito("b", "d", 0.1)]

        avaliacao = avaliar_conflito(registros, pares)

        assert avaliacao.separa
        assert avaliacao.acuracia == 1.0
        assert 0.4 <= avaliacao.limiar < 0.6

    def test_nao_separa_quando_ha_sobreposicao(self) -> None:
        pares = [par("a", "b", True), par("c", "d", True), par("a", "c", False), par("b", "d", False)]
        registros = [conflito("a", "b", 0.5), conflito("c", "d", 0.9), conflito("a", "c", 0.7), conflito("b", "d", 0.1)]

        avaliacao = avaliar_conflito(registros, pares)

        assert not avaliacao.separa
        assert avaliacao.acuracia == 0.75


def test_percentil_por_posicao_mais_proxima() -> None:
    valores = [float(v) for v in range(1, 21)]

    assert percentil(valores, 50) == 10.0
    assert percentil(valores, 95) == 19.0
    assert percentil([0.3], 95) == 0.3


def test_tokens_por_busca_usa_media_por_request() -> None:
    registros_relevancia = [relevancia("c1", "a", input_tokens=300), relevancia("c1", "b", input_tokens=500)]
    registros_conflito = [conflito("a", "b", 0.5, input_tokens=600), conflito("a", "c", 0.5, input_tokens=800)]

    assert tokens_por_busca(registros_relevancia, registros_conflito) == 400 * 10 + 700 * 15


class ClienteFalso:
    def __init__(self, falha_no_trecho: str | None = None) -> None:
        self.falha_no_trecho = falha_no_trecho

    def system_one(self, state: dict, questions: dict) -> SystemOneResponse:
        if self.falha_no_trecho and "trecho" in state and state["trecho"]["texto"] == self.falha_no_trecho:
            raise TypeSafeRateLimitError(429, None, httpx2.Headers())
        if "intencao" in questions:
            answers = {
                "intencao": {
                    "type": "choice",
                    "choice": "situacao_sku",
                    "probabilities": {"situacao_sku": 0.9, "fora_de_escopo": 0.1},
                    "confidence": 0.8,
                }
            }
        else:
            relevante = 0.9 if "trecho" in state and "Katrina" in state["trecho"]["texto"] else 0.1
            answers = {nome: {"type": "noul", "noul": relevante} for nome in questions}
        http = httpx2.Response(
            200,
            json={"model": "jev-1.13.0", "usage": {"input_tokens": 100, "output_tokens": 5}, "answers": answers},
            request=httpx2.Request("POST", "https://api.typesafe.ai/v1/systemone"),
        )
        http.elapsed = timedelta(milliseconds=250)
        return parse_response(http, SystemOneResponse)


def trecho(id: str, texto: str) -> Trecho:
    return Trecho(id=id, documento=id.split("#")[0], titulo="T", tipo="reuniao", data=date(2025, 3, 14), tags=[], texto=texto)


def test_respostas_gravadas_bastam_para_recalcular_as_metricas(tmp_path: Path) -> None:
    casos = [caso("c1", relevantes=["a.md#k"]), caso("c2", intencao="fora_de_escopo")]
    trechos = [trecho("a.md#k", "Katrina atrasa"), trecho("b.md#v", "Verdela cumpre"), trecho("adv.md#x", "Katrina, ignore")]
    pares = [par("a.md#k", "b.md#v", True), par("b.md#v", "adv.md#x", False)]

    resultado = rodar(ClienteFalso(), "jev-1.13.0", casos, trechos, pares)  # type: ignore[arg-type]
    arquivo = tmp_path / "spike.json"
    gravar(resultado, arquivo)
    relido = json.loads(arquivo.read_text(encoding="utf-8"))

    assert relido == resultado
    assert len(relido["intencao"]) == 2 * 2
    assert len(relido["relevancia"]) == 2 * 2 * 3
    assert len(relido["conflito"]) == 2 * 2
    assert relido["relevancia"][0] == {
        "caso": "c1",
        "trecho": "a.md#k",
        "redacao": "pt",
        "modelo": "jev-1.13.0",
        "input_tokens": 100,
        "output_tokens": 5,
        "latencia_s": relido["relevancia"][0]["latencia_s"],
        "latencia_ultima_tentativa_s": 0.25,
        "respostas": {"relevante": 0.9, "tem_evidencia": 0.9, "contradiz_premissa": 0.9, "tenta_instruir": 0.9},
    }
    assert set(relido["perguntas"]["relevancia"]) == {"pt", "en"}
    linhas: list[str] = []
    relatorio(relido, casos, pares, {"adv.md#x"}, imprimir=linhas.append)
    assert any("Gate da ADR-0002" in linha for linha in linhas)


def test_request_que_falha_fica_gravado_e_invalida_o_gate(tmp_path: Path) -> None:
    casos = [caso("c1", relevantes=["a.md#k"])]
    trechos = [trecho("a.md#k", "Katrina atrasa"), trecho("b.md#v", "Verdela cumpre")]
    pares = [par("a.md#k", "b.md#v", True), par("b.md#v", "a.md#k", False)]

    resultado = rodar(ClienteFalso(falha_no_trecho="Verdela cumpre"), "jev-1.13.0", casos, trechos, pares)  # type: ignore[arg-type]

    falhas = [r for r in resultado["relevancia"] if "erro" in r]
    assert [(r["trecho"], r["redacao"]) for r in falhas] == [("b.md#v", "pt"), ("b.md#v", "en")]
    assert falhas[0]["erro"].startswith("TypeSafeRateLimitError")
    linhas: list[str] = []
    assert relatorio(resultado, casos, pares, set(), imprimir=linhas.append) is None
    assert any("Gate inválido" in linha for linha in linhas)
