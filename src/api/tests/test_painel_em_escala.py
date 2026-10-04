"""O painel, a tela de Estoque, o painel do repositor e a varredura das notificações leem
o estoque inteiro num retrato em lote: o número de consultas ao banco não depende do número
de SKUs. Conta as consultas de `GET /painel`, `GET /estoque`, `GET /reposicao/painel` e
`GET /notificacoes` contra o Postgres, com o que já estiver no banco e com 30 SKUs a mais.
O tempo com 5.000 SKUs fica no benchmark (`scripts/benchmark_painel.py`), fora da suíte.
Pulado sem banco."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from src.db.engine import get_engine
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from tests.erp_no_banco import erp_no_banco
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.skus, copilot.avisos LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_disponivel(), reason="Postgres com schemas erp e copilot precisa estar disponível")

FORNECEDOR = make_fornecedor("Escala Têxtil")


def _mais_skus(quantos: int) -> InMemoryERPAdapter:
    skus = [make_sku(f"ESC-{n:04d}", produto_nome="Toalha Escala", cor=f"cor {n}") for n in range(quantos)]
    pedido = make_pedido_compra(FORNECEDOR, "enviado", key="escala", data_prevista_entrega=date(2026, 10, 1))
    hoje = datetime.now(UTC)
    return InMemoryERPAdapter(
        skus=skus,
        fornecedores=[FORNECEDOR],
        fornecedores_por_sku={s.sku_code: [make_fornecedor_sku(FORNECEDOR)] for s in skus},
        estoques={s.sku_code: make_estoque(disponivel=n % 7) for n, s in enumerate(skus)},
        vendas=[make_venda(s, hoje - timedelta(days=dias), 10) for s in skus for dias in (40, 70, 100, 200)],
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, s, quantidade=5) for s in skus[::3]],
    )


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)


def _consultas(client: TestClient, rota: str) -> int:
    consultas: list[str] = []

    def contar(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        consultas.append(statement)

    event.listen(get_engine(), "before_cursor_execute", contar)
    try:
        response = client.get(rota)
    finally:
        event.remove(get_engine(), "before_cursor_execute", contar)
    assert response.status_code == 200, response.text
    return len(consultas)


@pytest.mark.parametrize("rota", ["/painel", "/estoque", "/reposicao/painel"])
def test_faz_o_mesmo_numero_de_consultas_com_mais_skus(client: TestClient, rota: str) -> None:
    antes = _consultas(client, rota)

    with erp_no_banco(_mais_skus(30)):
        depois = _consultas(client, rota)

    assert depois == antes
    assert antes <= 13


@pytest.fixture
def sem_episodios() -> Iterator[None]:
    """A varredura grava episódios: guarda os do banco local e os devolve no fim."""
    with get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_episodios_escala AS SELECT * FROM copilot.episodios_alerta"))
        conn.execute(text("DELETE FROM copilot.episodios_alerta"))
        conn.commit()
        try:
            yield
        finally:
            conn.execute(text("DELETE FROM copilot.episodios_alerta"))
            conn.execute(text("INSERT INTO copilot.episodios_alerta SELECT * FROM backup_episodios_escala"))
            conn.execute(text("DROP TABLE backup_episodios_escala"))
            conn.commit()


def test_varredura_das_notificacoes_nao_consulta_por_sku(client: TestClient, sem_episodios: None) -> None:
    _consultas(client, "/notificacoes")
    sem_mudanca = _consultas(client, "/notificacoes")

    with erp_no_banco(_mais_skus(30)):
        abrindo = _consultas(client, "/notificacoes")
        sem_mudanca_com_mais_skus = _consultas(client, "/notificacoes")

    assert sem_mudanca_com_mais_skus == sem_mudanca
    assert abrindo == sem_mudanca + 1
    assert sem_mudanca <= 22
