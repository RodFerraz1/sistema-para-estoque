"""Testes HTTP de `POST /chat` e `GET /chat/registros` com ERP, política, busca,
Jev, redator e registros em memória."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.ai.dependencies import (
    get_decision_model,
    get_embedder,
    get_redator,
    get_registros_decisao,
    get_trechos_repositorio,
)
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel
from src.ai.registro import InMemoryRegistrosDecisao
from src.ai.schemas import Entendimento
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from tests.fakes import (
    RedatorGravador,
    make_entendimento,
    make_estoque,
    make_sku,
    make_trecho,
    repositorio_com,
)

SKU = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege")
PERGUNTA = "Qual a situação do SKU TBC-BEGE-70140-01?"
DEPENDENCIAS = (
    get_erp_adapter,
    get_politica_compra_repositorio,
    get_embedder,
    get_trechos_repositorio,
    get_decision_model,
    get_redator,
    get_registros_decisao,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def preparar(
    decisao: InMemoryDecisionModel | None = None, redator: RedatorGravador | None = None
) -> InMemoryRegistrosDecisao:
    """Sem `decisao`, o Jev fica o de verdade, que falha sem `JEV_KEY`. O redator
    e os registros são sempre trocados, para nenhum teste chamar o LLM nem gravar
    no banco."""
    embedder = FakeEmbedder()
    trechos = repositorio_com(
        [
            make_trecho("contratos/katrina.md#prazos", "lead time da Katrina"),
            make_trecho("reunioes/q1.md#katrina", "lead time da Katrina em dias"),
        ],
        embedder,
    )
    adapter = InMemoryERPAdapter(skus=[SKU], estoques={SKU.sku_code: make_estoque(disponivel=120)})
    politicas = InMemoryPoliticaCompraRepositorio()
    redator = redator or RedatorGravador()
    registros = InMemoryRegistrosDecisao()
    app.dependency_overrides[get_registros_decisao] = lambda: registros
    app.dependency_overrides[get_erp_adapter] = lambda: adapter
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: politicas
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_trechos_repositorio] = lambda: trechos
    app.dependency_overrides[get_redator] = lambda: redator
    if decisao is not None:
        app.dependency_overrides[get_decision_model] = lambda: decisao
    return registros


def jev(entendimento: Entendimento, **kwargs: object) -> InMemoryDecisionModel:
    return InMemoryDecisionModel(entendimento_padrao=entendimento, modelo="jev-1.13.0", **kwargs)


def test_chat_responde_a_situacao_do_sku(client: TestClient) -> None:
    registros = preparar(
        jev(
            make_entendimento(
                "situacao_sku",
                0.93,
                probabilidades_intencao={"situacao_sku": 0.93, "sugestao_compra": 0.07},
                modelo="jev-1.13.0",
            )
        ),
        RedatorGravador("A TBC-BEGE-70140-01 tem 120 unidades."),
    )

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 200
    body = response.json()
    [ficha] = body.pop("fichas")
    registro_id = body.pop("registro_id")
    assert ficha["sku_code"] == "TBC-BEGE-70140-01"
    assert ficha["estoque"]["quantidade_disponivel"] == 120
    assert body == {
        "resposta": "A TBC-BEGE-70140-01 tem 120 unidades.",
        "acao": "respondeu",
        "faixa": "alta",
        "entendimento": {
            "intencao": {
                "escolha": "situacao_sku",
                "confianca": 0.93,
                "probabilidades": {"situacao_sku": 0.93, "sugestao_compra": 0.07},
            },
            "produto": {"escolha": "nenhum", "confianca": 0.95, "probabilidades": {"nenhum": 0.95}},
            "modelo": "jev-1.13.0",
        },
        "identificacao": {
            "skus": ["TBC-BEGE-70140-01"],
            "total_skus": 1,
            "origem": "codigo",
            "produto": None,
            "candidatos": [],
        },
        "sugestoes": [],
        "trechos": [],
        "conflitos": [],
        "redator": "gravador",
    }
    [registro] = registros.listar(10)
    assert UUID(registro_id) == registro.id


def test_chat_devolve_os_trechos_e_os_conflitos_que_foram_ao_redator(client: TestClient) -> None:
    preparar(
        jev(
            make_entendimento("politica_ou_fornecedor", 0.9),
            padrao={"relevante": 0.9, "tem_evidencia": 0.9},
            conflitos={("contratos/katrina.md#prazos", "reunioes/q1.md#katrina"): 0.62},
        )
    )

    response = client.post("/chat", json={"pergunta": "lead time da Katrina"})

    assert response.status_code == 200
    body = response.json()
    assert body["identificacao"] is None
    assert {t["id"] for t in body["trechos"]} == {"contratos/katrina.md#prazos", "reunioes/q1.md#katrina"}
    assert body["trechos"][0]["classificacao"] == "aceito"
    assert body["trechos"][0]["avaliacao"]["relevante"] == 0.9
    [conflito] = body["conflitos"]
    assert conflito["probabilidade"] == 0.62


def test_esclarecimento_vem_sem_redator(client: TestClient) -> None:
    redator = RedatorGravador()
    preparar(jev(make_entendimento("situacao_sku", 0.3)), redator)

    response = client.post("/chat", json={"pergunta": "hmm"})

    assert response.status_code == 200
    assert response.json()["acao"] == "pediu_esclarecimento"
    assert response.json()["redator"] is None
    assert redator.chamadas == []


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({}, id="sem-pergunta"),
        pytest.param({"pergunta": ""}, id="pergunta-vazia"),
        pytest.param({"pergunta": "x" * 1001}, id="pergunta-com-1001-caracteres"),
    ],
)
def test_pergunta_fora_do_intervalo_da_422(client: TestClient, corpo: dict[str, str]) -> None:
    preparar(jev(make_entendimento()))

    assert client.post("/chat", json=corpo).status_code == 422


def test_pergunta_com_1000_caracteres_e_aceita(client: TestClient) -> None:
    preparar(jev(make_entendimento()))

    assert client.post("/chat", json={"pergunta": "x" * 1000}).status_code == 200


def test_jev_indisponivel_da_503(client: TestClient) -> None:
    preparar(jev(make_entendimento(), falhar_entendimento=True))

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 503
    assert response.json()["detail"]


def test_sem_jev_key_da_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_KEY", "")
    preparar()

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 503
    assert "JEV_KEY" in response.json()["detail"]


def test_registros_mostram_as_perguntas_respondidas_da_mais_recente(client: TestClient) -> None:
    preparar(
        jev(
            make_entendimento(
                "situacao_sku",
                0.93,
                probabilidades_intencao={"situacao_sku": 0.93, "sugestao_compra": 0.07},
                modelo="jev-1.13.0",
            )
        ),
        RedatorGravador("A TBC-BEGE-70140-01 tem 120 unidades."),
    )
    primeira = client.post("/chat", json={"pergunta": PERGUNTA}).json()
    segunda = client.post("/chat", json={"pergunta": "Como tá o estoque?"}).json()

    response = client.get("/chat/registros")

    assert response.status_code == 200
    recente, antigo = response.json()
    assert recente["id"] == segunda["registro_id"]
    assert recente["acao"] == "pediu_esclarecimento"
    assert recente["redator"] is None
    assert antigo["id"] == primeira["registro_id"]
    datetime.fromisoformat(antigo.pop("criado_em"))
    assert antigo.pop("duracao_ms") >= 0
    assert antigo == {
        "id": primeira["registro_id"],
        "pergunta": PERGUNTA,
        "intencao": "situacao_sku",
        "confianca": 0.93,
        "faixa": "alta",
        "acao": "respondeu",
        "skus": ["TBC-BEGE-70140-01"],
        "entendimento": primeira["entendimento"],
        "trechos": [],
        "redator": "gravador",
        "resposta": "A TBC-BEGE-70140-01 tem 120 unidades.",
    }


def test_registros_respeitam_o_limite(client: TestClient) -> None:
    preparar(jev(make_entendimento("fora_de_escopo", 0.95)))
    for i in range(3):
        client.post("/chat", json={"pergunta": f"pergunta {i}"})

    response = client.get("/chat/registros", params={"limite": 2})

    assert response.status_code == 200
    assert [r["pergunta"] for r in response.json()] == ["pergunta 2", "pergunta 1"]


def test_registros_sem_pergunta_devolvem_lista_vazia(client: TestClient) -> None:
    preparar()

    response = client.get("/chat/registros")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("limite", [0, 101])
def test_limite_fora_do_intervalo_da_422(client: TestClient, limite: int) -> None:
    preparar()

    assert client.get("/chat/registros", params={"limite": limite}).status_code == 422


def test_jev_indisponivel_nao_grava_registro(client: TestClient) -> None:
    registros = preparar(jev(make_entendimento(), falhar_entendimento=True))

    assert client.post("/chat", json={"pergunta": PERGUNTA}).status_code == 503
    assert registros.listar(10) == []
