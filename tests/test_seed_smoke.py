"""Smoke test do seed do ERP.

Verifica contagens esperadas por tabela, sanidade dos dados e idempotência.
Requer o banco Postgres do docker-compose rodando e `alembic upgrade head`
aplicado. Populamos o banco chamando `scripts.seed.run()`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from scripts.seed import run as run_seed
from src.db.engine import get_engine


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.produtos LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="Postgres com schema erp precisa estar disponível (docker compose up + alembic upgrade head)",
)


@pytest.fixture(scope="module", autouse=True)
def _seeded() -> None:
    run_seed()


def _fetch_one(sql: str) -> tuple:
    with get_engine().connect() as conn:
        return conn.execute(text(sql)).one()


def test_contagens_esperadas() -> None:
    (n_produtos,) = _fetch_one("SELECT count(*) FROM erp.produtos")
    (n_skus,) = _fetch_one("SELECT count(*) FROM erp.skus")
    (n_fornecedores,) = _fetch_one("SELECT count(*) FROM erp.fornecedores")
    (n_forn_skus,) = _fetch_one("SELECT count(*) FROM erp.fornecedores_skus")
    (n_snapshot,) = _fetch_one("SELECT count(*) FROM erp.estoque_snapshot")
    (n_pedidos,) = _fetch_one("SELECT count(*) FROM erp.pedidos_compra")

    assert n_produtos == 15
    assert 70 <= n_skus <= 90
    assert n_fornecedores == 5
    assert 160 <= n_forn_skus <= 220
    assert n_snapshot == n_skus
    assert n_pedidos == 15


def test_categorias_esperadas() -> None:
    with get_engine().connect() as conn:
        categorias = {
            row[0]
            for row in conn.execute(text("SELECT DISTINCT categoria FROM erp.produtos"))
        }
    assert categorias == {"felpudo", "jogo_cama", "mesa", "cozinha"}


def test_fornecedores_do_corpus() -> None:
    with get_engine().connect() as conn:
        nomes = {
            row[0] for row in conn.execute(text("SELECT nome FROM erp.fornecedores"))
        }
    for esperado in ("Katrina Têxtil", "Verdela Home", "Malha Fina"):
        assert esperado in nomes


def test_pedidos_em_estados_variados() -> None:
    with get_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT status::text FROM erp.pedidos_compra")
        ).all()
    status_presentes = {r[0] for r in rows}
    assert {"recebido_total", "enviado", "rascunho"}.issubset(status_presentes)


def test_todo_forn_sku_aponta_para_ids_validos() -> None:
    (invalidos,) = _fetch_one(
        """
        SELECT count(*)
        FROM erp.fornecedores_skus fs
        LEFT JOIN erp.fornecedores f ON f.id = fs.fornecedor_id
        LEFT JOIN erp.skus s ON s.id = fs.sku_id
        WHERE f.id IS NULL OR s.id IS NULL
        """
    )
    assert invalidos == 0


def test_estoque_nao_negativo() -> None:
    (negativos,) = _fetch_one(
        "SELECT count(*) FROM erp.estoque_snapshot WHERE quantidade_disponivel < 0"
    )
    assert negativos == 0


def test_giro_positivo_para_todo_sku() -> None:
    # Todo SKU deve ter vendido pelo menos algo em 24 meses.
    (skus_sem_venda,) = _fetch_one(
        """
        SELECT count(*)
        FROM erp.skus s
        LEFT JOIN erp.vendas v ON v.sku_id = s.id
        WHERE v.id IS NULL
        """
    )
    assert skus_sem_venda == 0


def test_movimentacoes_batem_com_snapshot() -> None:
    # A soma das movimentações (com sinal por tipo) tem que igualar o snapshot atual.
    (divergencias,) = _fetch_one(
        """
        WITH saldo AS (
            SELECT sku_id,
                   SUM(CASE
                       WHEN tipo IN ('entrada_compra', 'ajuste_positivo', 'devolucao')
                           THEN quantidade
                       ELSE -quantidade
                   END) AS saldo
            FROM erp.movimentacoes_estoque
            GROUP BY sku_id
        )
        SELECT count(*)
        FROM saldo
        JOIN erp.estoque_snapshot e USING (sku_id)
        WHERE saldo <> (e.quantidade_disponivel + e.quantidade_reservada)
        """
    )
    assert divergencias == 0


def test_cobertura_em_faixa_esperada() -> None:
    # Cobertura = estoque / giro (média mensal últimos 6 meses).
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                WITH giro AS (
                    SELECT sku_id, SUM(quantidade)::float / 6.0 AS media
                    FROM erp.vendas
                    WHERE data >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '6 months'
                    GROUP BY sku_id
                )
                SELECT s.sku_id,
                       (s.quantidade_disponivel + s.quantidade_reservada)::float
                           / NULLIF(g.media, 0) AS cobertura
                FROM erp.estoque_snapshot s
                LEFT JOIN giro g ON g.sku_id = s.sku_id
                """
            )
        ).all()

    coberturas = [r.cobertura for r in rows if r.cobertura is not None]
    assert coberturas, "Deveria haver cobertura calculável para algum SKU"
    # Pelo menos algumas coberturas na faixa esperada (0.5 - 4 meses).
    na_faixa = [c for c in coberturas if 0.3 <= c <= 6.0]
    assert len(na_faixa) / len(coberturas) >= 0.8


def test_sazonalidade_nov_dez_maior_que_fev_mar() -> None:
    (nov_dez,) = _fetch_one(
        """
        SELECT COALESCE(SUM(quantidade), 0)
        FROM erp.vendas
        WHERE EXTRACT(MONTH FROM data) IN (11, 12)
        """
    )
    (fev_mar,) = _fetch_one(
        """
        SELECT COALESCE(SUM(quantidade), 0)
        FROM erp.vendas
        WHERE EXTRACT(MONTH FROM data) IN (2, 3)
        """
    )
    assert nov_dez > fev_mar


def test_idempotencia_reseed() -> None:
    # Rodar o seed uma segunda vez deve deixar o banco no mesmo estado.
    (skus_antes,) = _fetch_one("SELECT count(*) FROM erp.skus")
    (mov_antes,) = _fetch_one("SELECT count(*) FROM erp.movimentacoes_estoque")
    (hash_antes,) = _fetch_one(
        "SELECT md5(string_agg(sku_code, ',' ORDER BY sku_code)) FROM erp.skus"
    )

    run_seed()

    (skus_depois,) = _fetch_one("SELECT count(*) FROM erp.skus")
    (mov_depois,) = _fetch_one("SELECT count(*) FROM erp.movimentacoes_estoque")
    (hash_depois,) = _fetch_one(
        "SELECT md5(string_agg(sku_code, ',' ORDER BY sku_code)) FROM erp.skus"
    )

    assert skus_antes == skus_depois
    assert mov_antes == mov_depois
    assert hash_antes == hash_depois
