"""Smoke da fila de aprovação contra o Postgres real com o seed.

O fluxo (gerar, aprovar, pedido no ERP, em trânsito descontado, rejeitar) roda com o
Jev trocado por um modelo fora do ar, para não ter custo: as sugestões entram sem
sinais. O teste `externo` gera a fila com o Jev real e confere os sinais.

Gerar a fila substitui as pendentes que já estavam no banco local. No fim, a fixture
`fila_do_smoke` apaga as linhas que o smoke gerou e os pedidos que ele criou no ERP (para
não mudar o em trânsito dos outros smokes) e devolve as pendentes substituídas para
`pendente`. Nada que o smoke não criou é apagado.
"""
from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from src.ai.dependencies import get_decision_model
from src.ai.in_memory import InMemoryDecisionModel
from src.api.schemas import ResultadoGeracaoResponse, SugestaoNaFilaResponse, SugestaoPedidoResponse
from src.db.engine import get_engine
from src.main import app

pytestmark = pytest.mark.smoke

SKU_DA_KATRINA = "TBC-BEGE-70140-01"


@pytest.fixture
def jev_fora_do_ar() -> Iterator[None]:
    app.dependency_overrides[get_decision_model] = lambda: InMemoryDecisionModel(
        falhar_trechos=True, falhar_sinais=True
    )
    yield
    app.dependency_overrides.pop(get_decision_model, None)


@pytest.fixture
def fila_do_smoke() -> Iterator[set[UUID]]:
    """Ids das linhas da fila que o smoke gerou; o teardown limpa o que elas criaram."""
    with get_engine().connect() as conn:
        pendentes_antes = conn.execute(
            text("SELECT id FROM copilot.sugestoes_fila WHERE status = 'pendente'")
        ).scalars().all()
    geradas: set[UUID] = set()
    yield geradas
    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM erp.pedidos_compra WHERE id IN (
                    SELECT pedido_compra_id FROM copilot.sugestoes_fila WHERE id = ANY(:geradas)
                )
                """
            ),
            {"geradas": list(geradas)},
        )
        conn.execute(text("DELETE FROM copilot.sugestoes_fila WHERE id = ANY(:geradas)"), {"geradas": list(geradas)})
        conn.execute(
            text("UPDATE copilot.sugestoes_fila SET status = 'pendente' WHERE id = ANY(:ids) AND status = 'substituida'"),
            {"ids": pendentes_antes},
        )


def _gerar(
    client: TestClient, geradas: set[UUID]
) -> tuple[ResultadoGeracaoResponse, list[SugestaoNaFilaResponse]]:
    response = client.post("/sugestoes/gerar")
    assert response.status_code == 200
    resultado = ResultadoGeracaoResponse.model_validate(response.json())
    pendentes = [SugestaoNaFilaResponse.model_validate(s) for s in client.get("/sugestoes").json()]
    geradas.update(p.id for p in pendentes)
    return resultado, pendentes


def _sugestao_atual(client: TestClient, sku_code: str) -> SugestaoPedidoResponse:
    response = client.get(f"/skus/{sku_code}/sugestao-compra")
    assert response.status_code == 200
    return SugestaoPedidoResponse.model_validate(response.json())


@pytest.mark.usefixtures("jev_fora_do_ar")
def test_gerar_aprovar_e_rejeitar_contra_o_seed(client: TestClient, fila_do_smoke: set[UUID]) -> None:
    with get_engine().connect() as conn:
        skus_ativos = conn.execute(text("SELECT count(*) FROM erp.skus WHERE ativo")).scalar_one()

    resultado, pendentes = _gerar(client, fila_do_smoke)

    assert resultado.skus_avaliados == skus_ativos
    assert resultado.sinais_indisponiveis
    assert resultado.geradas == len(pendentes) >= 2
    assert all(p.sugestao.sinais is None for p in pendentes)
    assert 0 < sum(p.destaque for p in pendentes) < len(pendentes)

    primeira, outra = pendentes[0], pendentes[1]
    sugerida = primeira.sugestao.sugestao
    assert sugerida.calculo is not None and sugerida.fornecedor is not None

    response = client.post(
        f"/sugestoes/{primeira.id}/aprovar",
        json={
            "aprovado_por": "Smoke do M7",
            "justificativa": "Smoke do M7." if primeira.faixa.exige_justificativa else None,
        },
    )

    assert response.status_code == 200
    aprovada = SugestaoNaFilaResponse.model_validate(response.json())
    assert aprovada.pedido_compra_id is not None
    assert aprovada.status == "aprovada"
    assert aprovada.quantidade_aprovada == sugerida.quantidade

    with get_engine().connect() as conn:
        pedido = conn.execute(
            text("SELECT status::text, fornecedor_id FROM erp.pedidos_compra WHERE id = :id"),
            {"id": aprovada.pedido_compra_id},
        ).one()
        itens = conn.execute(
            text(
                """
                SELECT s.sku_code, i.quantidade
                FROM erp.pedidos_compra_itens i JOIN erp.skus s ON s.id = i.sku_id
                WHERE i.pedido_id = :id
                """
            ),
            {"id": aprovada.pedido_compra_id},
        ).all()
    assert tuple(pedido) == ("aprovado", sugerida.fornecedor.fornecedor_id)
    assert [tuple(i) for i in itens] == [(primeira.sku_code, sugerida.quantidade)]

    seguinte = _sugestao_atual(client, primeira.sku_code)
    assert seguinte.calculo is not None
    assert seguinte.calculo.em_transito == sugerida.calculo.em_transito + sugerida.quantidade
    assert seguinte.quantidade < sugerida.quantidade

    assert client.post(f"/sugestoes/{primeira.id}/aprovar", json={"aprovado_por": "Smoke do M7"}).status_code == 409

    response = client.post(
        f"/sugestoes/{outra.id}/rejeitar",
        json={"rejeitado_por": "Smoke do M7", "motivo": "Smoke do M7: rejeição de teste."},
    )

    assert response.status_code == 200
    assert SugestaoNaFilaResponse.model_validate(response.json()).status == "rejeitada"
    rejeitada = SugestaoNaFilaResponse.model_validate(client.get(f"/sugestoes/{outra.id}").json())
    assert rejeitada.status == "rejeitada"
    assert rejeitada.motivo_rejeicao == "Smoke do M7: rejeição de teste."
    assert rejeitada.pedido_compra_id is None
    restantes = {s["id"] for s in client.get("/sugestoes").json()}
    assert str(primeira.id) not in restantes and str(outra.id) not in restantes
    assert len(restantes) == len(pendentes) - 2


@pytest.mark.externo
def test_gerar_com_o_jev_real_traz_os_sinais_do_corpus(client: TestClient, fila_do_smoke: set[UUID]) -> None:
    resultado, pendentes = _gerar(client, fila_do_smoke)

    assert not resultado.sinais_indisponiveis
    assert all(p.sugestao.sinais is not None for p in pendentes)
    assert 0 < sum(p.destaque for p in pendentes) < len(pendentes)
    katrina = next(p for p in pendentes if p.sku_code == SKU_DA_KATRINA)
    assert "atraso_do_fornecedor" in {s.tipo for s in katrina.sugestao.sinais or []}
