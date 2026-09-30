"""Smoke do `/chat` contra o Postgres real, com o Jev de verdade.

O primeiro teste troca o redator pelo `RedatorSemLLM` e é pulado sem `JEV_KEY`.
O segundo chama também a Groq e é pulado sem `GROQ_API_KEY`.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from src.ai.dependencies import get_redator
from src.ai.redator import RedatorSemLLM
from src.api.schemas import RegistroDecisaoResponse, RespostaChatResponse
from src.main import app

pytestmark = [pytest.mark.smoke, pytest.mark.externo]

PERGUNTA = "Qual a situação do SKU TBC-BEGE-70140-01?"


@pytest.fixture
def sem_llm() -> Iterator[None]:
    app.dependency_overrides[get_redator] = RedatorSemLLM
    yield
    app.dependency_overrides.pop(get_redator, None)


@pytest.mark.usefixtures("sem_llm")
def test_chat_com_jev_real_responde_a_situacao_do_sku_e_grava_o_registro(client: TestClient) -> None:
    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 200
    resposta = RespostaChatResponse.model_validate(response.json())
    assert resposta.entendimento.intencao.escolha == "situacao_sku"
    assert resposta.identificacao is not None
    assert resposta.identificacao.skus == ["TBC-BEGE-70140-01"]
    assert [f.sku_code for f in resposta.fichas] == ["TBC-BEGE-70140-01"]
    assert resposta.redator == "sem_llm"

    response = client.get("/chat/registros", params={"limite": 1})

    assert response.status_code == 200
    [registro] = [RegistroDecisaoResponse.model_validate(r) for r in response.json()]
    assert registro.id == resposta.registro_id
    assert registro.pergunta == PERGUNTA
    assert registro.intencao == "situacao_sku"
    assert registro.skus == ["TBC-BEGE-70140-01"]
    assert registro.redator == "sem_llm"
    assert registro.resposta == resposta.resposta


@pytest.mark.externo_llm
def test_chat_com_jev_e_groq_reais_redige_a_situacao_do_sku(client: TestClient) -> None:
    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 200
    resposta = RespostaChatResponse.model_validate(response.json())
    assert resposta.entendimento.intencao.escolha == "situacao_sku"
    assert resposta.identificacao is not None
    assert resposta.identificacao.skus == ["TBC-BEGE-70140-01"]
    assert resposta.redator is not None and resposta.redator.startswith("groq:")
    assert resposta.resposta.strip()
