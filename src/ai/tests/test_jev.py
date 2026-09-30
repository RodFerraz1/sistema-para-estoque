"""Testes do `JevDecisionModel` com um cliente TypeSafe falso no lugar da API.

O último teste chama o Jev real (marcador `externo`) e é pulado sem `JEV_KEY`.
"""
from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

import pytest
from typesafe_sdk import JSONContent, Noul, Question, SystemOneResponse, TypeSafeAPITimeoutError

from src.ai.busca import LIMIARES
from src.ai.corpus import ler_corpus
from src.ai.decisao import DecisaoIndisponivel
from src.ai.jev import JevDecisionModel, criar_cliente
from src.ai.schemas import Trecho
from src.db.config import get_settings

RAIZ = Path(__file__).resolve().parents[3]
EVALS = RAIZ / "evals"
SPIKE_R2 = EVALS / "resultados" / "spike-2026-09-30-r2.json"


class ClienteFalso:
    """Responde cada `Noul` com o valor de `respostas` para o nome da pergunta, ou 0,5.

    Com `falha_no_texto`, dá timeout nos pedidos cujo trecho tem esse texto.
    """

    def __init__(
        self,
        respostas: Mapping[str, float] | None = None,
        modelo: str = "jev-1.13.0",
        falha_no_texto: str | None = None,
    ) -> None:
        self.respostas = respostas or {}
        self.modelo = modelo
        self.falha_no_texto = falha_no_texto
        self.pedidos: list[tuple[JSONContent, dict[str, Question]]] = []

    def system_one(self, state: JSONContent, questions: Mapping[str, Question]) -> SystemOneResponse:
        self.pedidos.append((state, dict(questions)))
        if self.falha_no_texto is not None and self.falha_no_texto in json.dumps(state, ensure_ascii=False):
            raise TypeSafeAPITimeoutError(10.0)
        return SystemOneResponse.model_validate(
            {
                "model": self.modelo,
                "usage": {"input_tokens": 100, "output_tokens": 4},
                "answers": {
                    nome: {"type": "noul", "noul": self.respostas.get(nome, 0.5)} for nome in questions
                },
            }
        )


def trecho(id: str, texto: str) -> Trecho:
    return Trecho(
        id=id,
        documento=id.split("#")[0],
        titulo=f"Katrina Têxtil S.A. > {id}",
        tipo="fornecedor",
        data=date(2025, 11, 10),
        tags=["katrina"],
        texto=texto,
    )


def test_cada_trecho_vai_com_a_pergunta_e_depois_sozinho_para_a_injecao() -> None:
    cliente = ClienteFalso()
    lead_time = trecho("fornecedores/katrina.md#lead-time", "Contratado 45 dias, observado 62.")

    JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", [lead_time])

    no_state = {
        "titulo": "Katrina Têxtil S.A. > fornecedores/katrina.md#lead-time",
        "tipo": "fornecedor",
        "data": "2025-11-10",
        "texto": "Contratado 45 dias, observado 62.",
    }
    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        (
            {"pergunta": "lead time da Katrina", "trecho": no_state},
            ["contradiz_premissa", "relevante", "tem_evidencia"],
        ),
        ({"trecho": no_state}, ["tenta_instruir"]),
    ]


def test_perguntas_sao_as_calibradas_no_spike_em_pt() -> None:
    cliente = ClienteFalso()
    calibradas = json.loads(SPIKE_R2.read_text(encoding="utf-8"))["perguntas"]

    jev = JevDecisionModel(cliente)
    jev.avaliar_trechos("lead time da Katrina", [trecho("a.md#s", "Texto.")])
    jev.avaliar_conflitos([(trecho("a.md#s", "Texto."), trecho("b.md#s", "Outro texto."))])

    enviadas = [
        {nome: p.model_dump() for nome, p in perguntas.items() if isinstance(p, Noul)}
        for _, perguntas in cliente.pedidos
    ]
    assert enviadas == [
        calibradas["relevancia"]["pt"],
        calibradas["injecao"]["pt"],
        calibradas["conflito"]["pt"],
    ]


def test_cada_resposta_vira_o_campo_de_mesmo_nome_na_ordem_dos_trechos() -> None:
    cliente = ClienteFalso(
        {"relevante": 0.91, "tem_evidencia": 0.82, "contradiz_premissa": 0.13, "tenta_instruir": 0.04}
    )
    trechos = [trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(12)]

    avaliacoes = JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", trechos)

    assert [a.trecho_id for a in avaliacoes] == [t.id for t in trechos]
    assert {
        (a.relevante, a.tem_evidencia, a.contradiz_premissa, a.tenta_instruir) for a in avaliacoes
    } == {(0.91, 0.82, 0.13, 0.04)}


def test_modelo_vem_da_resposta_do_jev() -> None:
    cliente = ClienteFalso(modelo="jev-1.13.1")

    [avaliacao] = JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", [trecho("a.md#s", "Texto.")])

    assert avaliacao.modelo == "jev-1.13.1"


def test_erro_do_sdk_num_trecho_vira_decisao_indisponivel_para_o_lote_todo() -> None:
    cliente = ClienteFalso(falha_no_texto="Texto 3.")
    trechos = [trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(6)]

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", trechos)


def test_cada_par_vai_num_request_com_os_dois_trechos_no_state() -> None:
    cliente = ClienteFalso()
    contrato = trecho("contratos/katrina.md#prazos", "Antecedência mínima de 45 dias.")
    revisao = trecho("reunioes/q1.md#katrina", "Lead time observado de 62 dias.")

    JevDecisionModel(cliente).avaliar_conflitos([(contrato, revisao)])

    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        (
            {
                "trecho_a": {
                    "titulo": "Katrina Têxtil S.A. > contratos/katrina.md#prazos",
                    "tipo": "fornecedor",
                    "data": "2025-11-10",
                    "texto": "Antecedência mínima de 45 dias.",
                },
                "trecho_b": {
                    "titulo": "Katrina Têxtil S.A. > reunioes/q1.md#katrina",
                    "tipo": "fornecedor",
                    "data": "2025-11-10",
                    "texto": "Lead time observado de 62 dias.",
                },
            },
            ["conflitam"],
        )
    ]


def test_cada_par_vira_a_probabilidade_de_conflito_na_ordem_dos_pares() -> None:
    cliente = ClienteFalso({"conflitam": 0.62}, modelo="jev-1.13.1")
    pares = [(trecho(f"a.md#s{i}", f"Texto {i}."), trecho(f"b.md#s{i}", f"Outro {i}.")) for i in range(12)]

    avaliacoes = JevDecisionModel(cliente).avaliar_conflitos(pares)

    assert [(a.trecho_a, a.trecho_b) for a in avaliacoes] == [(x.id, y.id) for x, y in pares]
    assert {(a.conflitam, a.modelo) for a in avaliacoes} == {(0.62, "jev-1.13.1")}


def test_erro_do_sdk_num_par_vira_decisao_indisponivel_para_o_lote_todo() -> None:
    cliente = ClienteFalso(falha_no_texto="Outro 3.")
    pares = [(trecho(f"a.md#s{i}", f"Texto {i}."), trecho(f"b.md#s{i}", f"Outro {i}.")) for i in range(6)]

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).avaliar_conflitos(pares)


@pytest.fixture
def jev_real() -> Iterator[JevDecisionModel]:
    settings = get_settings()
    if not settings.jev_key:
        pytest.skip("JEV_KEY vazio: não chama o Jev real")
    with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
        yield JevDecisionModel(cliente)


@pytest.mark.externo
def test_jev_real_aceita_o_lead_time_da_katrina_e_pega_a_injecao(jev_real: JevDecisionModel) -> None:
    lead_time = next(
        t for t in ler_corpus(RAIZ / "corpus") if t.id == "fornecedores/katrina-textil.md#lead-time"
    )
    adversarial = next(
        Trecho.model_validate(item)
        for item in json.loads((EVALS / "trechos_adversariais.json").read_text(encoding="utf-8"))
        if item["id"] == "adversarial/reunioes/2025-06-alinhamento-katrina.md#decisoes"
    )

    do_lead_time, do_adversarial = jev_real.avaliar_trechos(
        "Qual o lead time de verdade da Katrina?", [lead_time, adversarial]
    )

    assert do_lead_time.modelo == "jev-1.13.0"
    assert do_lead_time.relevante >= LIMIARES.relevante
    assert do_lead_time.tem_evidencia > LIMIARES.evidencia
    assert do_lead_time.tenta_instruir <= LIMIARES.injecao
    assert do_adversarial.tenta_instruir > LIMIARES.injecao


@pytest.mark.externo
def test_jev_real_sinaliza_o_conflito_do_lead_time_da_katrina(jev_real: JevDecisionModel) -> None:
    por_id = {t.id: t for t in ler_corpus(RAIZ / "corpus")}
    nota_interna = por_id["contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato"]
    revisao_q1 = por_id["reunioes/2025-q1-revisao-fornecedores.md#katrina-textil"]

    [avaliacao] = jev_real.avaliar_conflitos([(nota_interna, revisao_q1)])

    assert avaliacao.modelo == "jev-1.13.0"
    assert avaliacao.conflitam > LIMIARES.conflito
