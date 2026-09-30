"""Smoke do `/chat` contra o Postgres real, com o Jev e a Groq de verdade.

Pulado sem `JEV_KEY` ou sem `GROQ_API_KEY`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.schemas import RespostaChatResponse

pytestmark = [pytest.mark.smoke, pytest.mark.externo, pytest.mark.externo_llm]


def test_chat_com_jev_e_groq_reais_redige_a_situacao_do_sku(client: TestClient) -> None:
    response = client.post("/chat", json={"pergunta": "Qual a situação do SKU TBC-BEGE-70140-01?"})

    assert response.status_code == 200
    resposta = RespostaChatResponse.model_validate(response.json())
    assert resposta.entendimento.intencao.escolha == "situacao_sku"
    assert resposta.identificacao is not None
    assert resposta.identificacao.skus == ["TBC-BEGE-70140-01"]
    assert resposta.redator is not None and resposta.redator.startswith("groq:")
    assert resposta.resposta.strip()
