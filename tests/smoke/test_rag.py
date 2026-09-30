"""Smoke do RAG: ingestão do `corpus/` e `/rag/busca` contra o Postgres real.

A busca chama o Jev de verdade e é pulada sem `JEV_KEY`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.ai.corpus import ler_corpus
from src.ai.dependencies import get_embedder, get_trechos_repositorio
from src.ai.ingestao import ingerir
from src.api.schemas import ResultadoBuscaResponse
from src.db.config import get_settings

pytestmark = pytest.mark.smoke


def test_segunda_ingestao_deixa_todo_o_corpus_inalterado() -> None:
    pasta = get_settings().corpus_dir

    relatorio = ingerir(pasta, get_embedder(), get_trechos_repositorio())

    assert (relatorio.novos, relatorio.alterados, relatorio.removidos) == ([], [], [])
    assert sorted(relatorio.inalterados) == sorted({t.documento for t in ler_corpus(pasta)})


@pytest.mark.externo
@pytest.mark.skipif(not get_settings().jev_key, reason="JEV_KEY vazio: não chama o Jev real")
def test_busca_do_lead_time_da_katrina_aceita_um_trecho_da_katrina(client: TestClient) -> None:
    response = client.get("/rag/busca", params={"q": "lead time da Katrina"})

    assert response.status_code == 200
    resultado = ResultadoBuscaResponse.model_validate(response.json())
    assert any(t.classificacao == "aceito" and "katrina" in t.documento for t in resultado.trechos)
