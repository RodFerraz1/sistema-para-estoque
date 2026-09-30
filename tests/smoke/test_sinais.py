"""Smoke dos sinais do corpus contra o Postgres real, com o Jev de verdade."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.schemas import SinalCorpusResponse

pytestmark = [pytest.mark.smoke, pytest.mark.externo]


def test_sinais_de_um_sku_da_katrina_trazem_o_atraso_do_fornecedor(client: TestClient) -> None:
    response = client.get("/skus/TBC-BEGE-70140-01/sugestao-compra/sinais")

    assert response.status_code == 200
    sinais = {s.tipo: s for s in (SinalCorpusResponse.model_validate(item) for item in response.json())}
    assert "atraso_do_fornecedor" in sinais
    assert sinais["atraso_do_fornecedor"].mensagem == "Os documentos relatam atraso de entrega da Katrina Têxtil."
