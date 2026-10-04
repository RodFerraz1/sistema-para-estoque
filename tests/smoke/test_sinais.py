"""Smoke dos sinais do corpus contra o Postgres real, com o Jev de verdade. O chat
troca o redator pelo `RedatorSemLLM`, para não depender do LLM."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from scripts.seed import RUPTURA_SEM_PEDIDO
from src.ai.dependencies import get_redator
from src.ai.redator import RedatorSemLLM
from src.api.schemas import RegistroDecisaoResponse, RespostaChatResponse, SinalCorpusResponse
from src.main import app

pytestmark = [pytest.mark.smoke, pytest.mark.externo]

# Cenário do seed: em ruptura, sem pedido, com a Katrina como fornecedor mais barato.
SKU_DA_KATRINA = RUPTURA_SEM_PEDIDO
ATRASO_DA_KATRINA = "Os documentos relatam atraso de entrega da Katrina Têxtil."


@pytest.fixture
def sem_llm() -> Iterator[None]:
    app.dependency_overrides[get_redator] = lambda: RedatorSemLLM()
    yield
    app.dependency_overrides.pop(get_redator, None)


def test_sinais_de_um_sku_da_katrina_trazem_o_atraso_do_fornecedor(client: TestClient) -> None:
    response = client.get(f"/skus/{SKU_DA_KATRINA}/sugestao-compra/sinais")

    assert response.status_code == 200
    sinais = {s.tipo: s for s in (SinalCorpusResponse.model_validate(item) for item in response.json())}
    assert "atraso_do_fornecedor" in sinais
    assert sinais["atraso_do_fornecedor"].mensagem == ATRASO_DA_KATRINA


@pytest.mark.usefixtures("sem_llm")
def test_chat_pedindo_sugestao_do_sku_da_katrina_traz_os_sinais(client: TestClient) -> None:
    response = client.post("/chat", json={"pergunta": f"Quanto devo comprar do SKU {SKU_DA_KATRINA}?"})

    assert response.status_code == 200
    resposta = RespostaChatResponse.model_validate(response.json())
    assert resposta.entendimento.intencao.escolha == "sugestao_compra"
    [sugestao] = resposta.sugestoes
    assert sugestao.sugestao.sku_code == SKU_DA_KATRINA
    atraso = next(s for s in sugestao.sinais if s.tipo == "atraso_do_fornecedor")
    assert atraso.mensagem == ATRASO_DA_KATRINA
    assert set(atraso.trechos) & {t.id for t in resposta.trechos}
    assert ATRASO_DA_KATRINA in resposta.resposta
    assert resposta.citacoes == []

    [registro] = [RegistroDecisaoResponse.model_validate(r) for r in client.get("/chat/registros?limite=1").json()]
    assert registro.id == resposta.registro_id
    assert [s.sku_code for s in registro.sinais] == [SKU_DA_KATRINA]
