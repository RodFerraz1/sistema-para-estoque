"""Testes de integração do `PostgresERPAdapter` contra Postgres real.

Requerem `docker compose up` + `alembic upgrade head` + seed populado.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from scripts.seed import run as run_seed
from src.db.engine import get_engine
from src.erp_adapter.postgres import PostgresERPAdapter
from src.erp_adapter.schemas import FiltrosSKU


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.produtos LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="Postgres com schema erp precisa estar disponível",
)


@pytest.fixture(scope="module", autouse=True)
def _seeded() -> None:
    run_seed()


@pytest.fixture(scope="module")
def adapter() -> PostgresERPAdapter:
    return PostgresERPAdapter(get_engine())


def _algum_sku_code() -> str:
    with get_engine().connect() as conn:
        (code,) = conn.execute(
            text("SELECT sku_code FROM erp.skus ORDER BY sku_code LIMIT 1")
        ).one()
    return code


def test_get_sku_raw_por_codigo(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()

    sku = adapter.get_sku_raw_por_codigo(code)

    assert sku is not None
    assert sku.sku_code == code
    assert sku.produto_nome
    assert sku.produto_categoria in {"felpudo", "jogo_cama", "mesa", "cozinha"}


def test_get_sku_raw_por_codigo_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.get_sku_raw_por_codigo("NAO-EXISTE-XYZ") is None


def test_get_sku_raw_por_id(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    encontrado = adapter.get_sku_raw_por_codigo(code)
    assert encontrado is not None

    por_id = adapter.get_sku_raw(encontrado.id)

    assert por_id is not None
    assert por_id.id == encontrado.id


def test_list_skus_raw_filtra_categoria(adapter: PostgresERPAdapter) -> None:
    skus = adapter.list_skus_raw(FiltrosSKU(categoria="felpudo"))

    assert skus, "seed deve ter SKUs felpudos"
    assert all(s.produto_categoria == "felpudo" for s in skus)


def test_list_skus_raw_sem_filtros(adapter: PostgresERPAdapter) -> None:
    skus = adapter.list_skus_raw(FiltrosSKU())

    assert 70 <= len(skus) <= 90


def test_list_fornecedores_para_sku(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.get_sku_raw_por_codigo(code)
    assert sku is not None

    fornecedores = adapter.list_fornecedores_para_sku(sku.id)

    assert fornecedores, "SKU do seed deve ter fornecedores"
    precos = [f.preco_unitario_atual for f in fornecedores]
    assert precos == sorted(precos), "ordenado por preço ascendente"
    assert all(f.fornecedor_nome for f in fornecedores)


def test_get_fornecedor_raw(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.get_sku_raw_por_codigo(code)
    assert sku is not None
    fornecedores = adapter.list_fornecedores_para_sku(sku.id)
    assert fornecedores

    fornecedor = adapter.get_fornecedor_raw(fornecedores[0].fornecedor_id)

    assert fornecedor is not None
    assert fornecedor.nome == fornecedores[0].fornecedor_nome
    assert fornecedor.ativo is True


def test_get_estoque_atual(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.get_sku_raw_por_codigo(code)
    assert sku is not None

    estoque = adapter.get_estoque_atual(sku.id)

    assert estoque is not None
    assert estoque.quantidade_disponivel >= 0
    assert estoque.quantidade_reservada >= 0


def test_list_movimentacoes(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.get_sku_raw_por_codigo(code)
    assert sku is not None
    desde = datetime(2024, 1, 1, tzinfo=UTC)

    movs = adapter.list_movimentacoes(sku.id, desde)

    assert movs, "seed deve gerar movimentações para todo SKU"
    assert all(m.sku_id == sku.id for m in movs)
    assert all(m.data >= desde for m in movs)
    tipos = {m.tipo for m in movs}
    assert tipos.issubset(
        {
            "entrada_compra",
            "saida_venda",
            "ajuste_positivo",
            "ajuste_negativo",
            "devolucao",
        }
    )


def test_list_vendas(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.get_sku_raw_por_codigo(code)
    assert sku is not None
    desde = datetime(2024, 1, 1, tzinfo=UTC)

    vendas = adapter.list_vendas(sku.id, desde)

    assert vendas, "seed deve gerar vendas para todo SKU"
    assert all(v.quantidade > 0 for v in vendas)
    assert all(v.data >= desde for v in vendas)
