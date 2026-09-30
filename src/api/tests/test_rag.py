"""Testes HTTP de `/rag/busca` com embedder, repositório e Jev em memória."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.ai.decisao import DecisionModel
from src.ai.dependencies import get_decision_model, get_embedder, get_trechos_repositorio
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel, InMemoryTrechosRepositorio
from src.ai.schemas import Trecho, TrechoIndexado
from src.main import app

PERGUNTA = "lead time da Katrina"


def trecho(id: str, texto: str = PERGUNTA) -> Trecho:
    return Trecho(
        id=id,
        documento=id.split("#")[0],
        titulo=f"Katrina Têxtil S.A. > {id}",
        tipo="fornecedor",
        data=date(2025, 11, 10),
        tags=["katrina", "lead-time"],
        texto=texto,
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in (get_embedder, get_trechos_repositorio, get_decision_model):
        app.dependency_overrides.pop(dependencia, None)


def preparar(trechos: list[Trecho], decisao: DecisionModel | None = None) -> None:
    """Indexa `trechos` em memória e, com `decisao`, troca o Jev por ela."""
    embedder = FakeEmbedder()
    repositorio = InMemoryTrechosRepositorio()
    por_documento: dict[str, list[TrechoIndexado]] = defaultdict(list)
    for t, vetor in zip(trechos, embedder.embed([t.texto for t in trechos]), strict=True):
        por_documento[t.documento].append(TrechoIndexado(**t.model_dump(), embedding=vetor))
    for documento, indexados in por_documento.items():
        repositorio.substituir_documento(documento, f"hash de {documento}", indexados)
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_trechos_repositorio] = lambda: repositorio
    if decisao is not None:
        app.dependency_overrides[get_decision_model] = lambda: decisao


def test_busca_devolve_os_trechos_classificados_com_as_probabilidades(client: TestClient) -> None:
    preparar(
        [trecho("fornecedores/katrina.md#lead-time")],
        InMemoryDecisionModel(
            {
                "fornecedores/katrina.md#lead-time": {
                    "relevante": 0.91,
                    "tem_evidencia": 0.82,
                    "contradiz_premissa": 0.13,
                    "tenta_instruir": 0.04,
                }
            },
            modelo="jev-1.13.0",
        ),
    )

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 200
    body = response.json()
    [item] = body.pop("trechos")
    assert body == {"pergunta": PERGUNTA, "modelo": "jev-1.13.0", "conflitos": []}
    assert item.pop("similaridade") == pytest.approx(1.0)
    assert item == {
        "id": "fornecedores/katrina.md#lead-time",
        "documento": "fornecedores/katrina.md",
        "titulo": "Katrina Têxtil S.A. > fornecedores/katrina.md#lead-time",
        "tipo": "fornecedor",
        "data": "2025-11-10",
        "tags": ["katrina", "lead-time"],
        "texto": PERGUNTA,
        "classificacao": "aceito",
        "motivo_descarte": None,
        "avaliacao": {
            "relevante": 0.91,
            "tem_evidencia": 0.82,
            "contradiz_premissa": 0.13,
            "tenta_instruir": 0.04,
        },
    }


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({}, id="sem-q"),
        pytest.param({"q": ""}, id="q-vazio"),
        pytest.param({"q": "x" * 501}, id="q-com-501-caracteres"),
        pytest.param({"q": PERGUNTA, "k": 0}, id="k-0"),
        pytest.param({"q": PERGUNTA, "k": 41}, id="k-41"),
    ],
)
def test_parametros_fora_do_intervalo_dao_422(
    client: TestClient, params: dict[str, str | int]
) -> None:
    preparar([trecho("a.md#s")], InMemoryDecisionModel())

    assert client.get("/rag/busca", params=params).status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"q": "x" * 500}, id="q-com-500-caracteres"),
        pytest.param({"q": PERGUNTA, "k": 1}, id="k-1"),
        pytest.param({"q": PERGUNTA, "k": 40}, id="k-40"),
    ],
)
def test_parametros_nos_limites_sao_aceitos(
    client: TestClient, params: dict[str, str | int]
) -> None:
    preparar([trecho("a.md#s")], InMemoryDecisionModel())

    assert client.get("/rag/busca", params=params).status_code == 200


def test_sem_k_avalia_os_30_mais_parecidos(client: TestClient) -> None:
    preparar([trecho(f"a.md#s{i}", f"lead time {i}") for i in range(31)], InMemoryDecisionModel())

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 200
    assert len(response.json()["trechos"]) == 30


def test_busca_devolve_os_conflitos_entre_trechos(client: TestClient) -> None:
    preparar(
        [
            trecho("contratos/katrina.md#prazos", "lead time da Katrina"),
            trecho("reunioes/q1.md#katrina", "lead time da Katrina em dias"),
        ],
        InMemoryDecisionModel(
            padrao={"relevante": 0.9, "tem_evidencia": 0.9},
            conflitos={("contratos/katrina.md#prazos", "reunioes/q1.md#katrina"): 0.62},
        ),
    )

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 200
    assert response.json()["conflitos"] == [
        {
            "trecho_a": "contratos/katrina.md#prazos",
            "trecho_b": "reunioes/q1.md#katrina",
            "probabilidade": 0.62,
        }
    ]


@pytest.mark.parametrize(
    "decisao",
    [
        pytest.param(InMemoryDecisionModel(falhar_trechos=True), id="nos-trechos"),
        pytest.param(
            InMemoryDecisionModel(
                padrao={"relevante": 0.9, "tem_evidencia": 0.9}, falhar_conflitos=True
            ),
            id="no-conflito",
        ),
    ],
)
def test_jev_indisponivel_da_503(client: TestClient, decisao: InMemoryDecisionModel) -> None:
    preparar([trecho("a.md#s"), trecho("b.md#s", "lead time da Katrina em dias")], decisao)

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 503
    assert response.json()["detail"]


def test_sem_jev_key_da_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_KEY", "")
    preparar([trecho("a.md#s")])

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 503
    assert "JEV_KEY" in response.json()["detail"]


def test_corpus_vazio_da_200_com_listas_vazias(client: TestClient) -> None:
    preparar([], InMemoryDecisionModel())

    response = client.get("/rag/busca", params={"q": PERGUNTA})

    assert response.status_code == 200
    assert response.json() == {"pergunta": PERGUNTA, "modelo": None, "trechos": [], "conflitos": []}
