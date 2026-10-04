"""Smoke test do seed do ERP.

Verifica contagens esperadas por tabela, sanidade dos dados e idempotência.
Requer o banco Postgres do docker-compose rodando e `alembic upgrade head`
aplicado. Populamos o banco chamando `scripts.seed.run()`.
"""
from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from scripts.seed import (
    QUEDA_SEM_ESTOQUE,
    RUPTURA_COM_PEDIDO_ATRASADO,
    RUPTURA_SEM_PEDIDO,
    TAPETE_BRANCO,
    TAPETE_MARROM,
)
from scripts.seed import run as run_seed
from src.db.engine import get_engine

HOJE = datetime.now(UTC).date()
INICIO_DIARIO = HOJE - timedelta(days=90)


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.produtos LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not _db_available(),
        reason="Postgres com schema erp precisa estar disponível (docker compose up + alembic upgrade head)",
    ),
]


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

    assert n_produtos == 16
    assert 70 <= n_skus <= 90
    assert n_fornecedores == 5
    assert 160 <= n_forn_skus <= 220
    assert n_snapshot == n_skus
    assert n_pedidos == 16


def test_categorias_esperadas() -> None:
    with get_engine().connect() as conn:
        categorias = {
            row[0]
            for row in conn.execute(text("SELECT DISTINCT categoria FROM erp.produtos"))
        }
    assert categorias == {"felpudo", "jogo_cama", "mesa", "cozinha", "banho"}


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


def test_vendas_diarias_nos_ultimos_90_dias_sem_domingo() -> None:
    with get_engine().connect() as conn:
        linhas = conn.execute(
            text(
                """
                SELECT s.sku_code, (v.data AT TIME ZONE 'UTC')::date AS dia, count(*) AS n
                FROM erp.vendas v JOIN erp.skus s ON s.id = v.sku_id
                WHERE v.data >= :inicio
                GROUP BY 1, 2
                """
            ),
            {"inicio": INICIO_DIARIO},
        ).all()
        (n_skus,) = conn.execute(text("SELECT count(*) FROM erp.skus")).one()

    dias = {linha.dia for linha in linhas}
    abertos = {
        INICIO_DIARIO + timedelta(days=d)
        for d in range(90)
        if (INICIO_DIARIO + timedelta(days=d)).weekday() != 6
    }
    assert dias == abertos
    assert all(linha.n == 1 for linha in linhas)
    assert len(linhas) > 0.6 * n_skus * len(abertos)


def test_todo_sku_vendeu_no_mes_passado() -> None:
    fim = HOJE.replace(day=1)
    inicio = (fim - timedelta(days=1)).replace(day=1)
    (sem_venda,) = _fetch_one(
        f"""
        SELECT count(*) FROM erp.skus s
        WHERE NOT EXISTS (
            SELECT 1 FROM erp.vendas v
            WHERE v.sku_id = s.id AND v.data >= '{inicio}' AND v.data < '{fim}'
        )
        """
    )
    assert sem_venda == 0


def _dias_abertos_antes_de_hoje(n: int) -> list[date]:
    dias = [HOJE - timedelta(days=d) for d in range(1, 2 * n)]
    return sorted(dia for dia in dias if dia.weekday() != 6)[-n:]


def _vendas_por_dia() -> dict[str, dict[date, int]]:
    with get_engine().connect() as conn:
        linhas = conn.execute(
            text(
                """
                SELECT s.sku_code, (v.data AT TIME ZONE 'UTC')::date AS dia, sum(v.quantidade) AS qtd
                FROM erp.vendas v JOIN erp.skus s ON s.id = v.sku_id
                WHERE v.data >= :inicio
                GROUP BY 1, 2
                """
            ),
            {"inicio": INICIO_DIARIO},
        ).all()
    vendas: dict[str, dict[date, int]] = {}
    for linha in linhas:
        vendas.setdefault(linha.sku_code, {})[linha.dia] = linha.qtd
    return vendas


def _janela_e_lambda(vendas: dict[date, int]) -> tuple[list[int], float]:
    """As vendas dos dois últimos dias abertos e a média dos 28 dias abertos anteriores."""
    dias = _dias_abertos_antes_de_hoje(30)
    base = sum(vendas.get(dia, 0) for dia in dias[:28]) / 28
    return [vendas.get(dia, 0) for dia in dias[28:]], base


def _poisson_ate(k: int, media: float) -> float:
    return sum(math.exp(-media) * media**i / math.factorial(i) for i in range(k + 1))


def _disponivel(sku_code: str) -> int:
    (disponivel,) = _fetch_one(
        f"""
        SELECT e.quantidade_disponivel FROM erp.estoque_snapshot e
        JOIN erp.skus s ON s.id = e.sku_id WHERE s.sku_code = '{sku_code}'
        """
    )
    return disponivel


def _cobertura_dias(sku_code: str) -> float:
    fim = HOJE.replace(day=1)
    inicio = date(fim.year - (fim.month <= 6), (fim.month - 7) % 12 + 1, 1)
    (vendido,) = _fetch_one(
        f"""
        SELECT sum(v.quantidade) FROM erp.vendas v JOIN erp.skus s ON s.id = v.sku_id
        WHERE s.sku_code = '{sku_code}' AND v.data >= '{inicio}' AND v.data < '{fim}'
        """
    )
    return _disponivel(sku_code) / (vendido / 6 / 30)


def _em_pedido_aberto(sku_code: str) -> list[tuple]:
    with get_engine().connect() as conn:
        return [
            tuple(linha)
            for linha in conn.execute(
                text(
                    """
                    SELECT p.status::text, f.nome, p.data_prevista_entrega,
                           i.quantidade - i.quantidade_recebida
                    FROM erp.pedidos_compra_itens i
                    JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                    JOIN erp.fornecedores f ON f.id = p.fornecedor_id
                    JOIN erp.skus s ON s.id = i.sku_id
                    WHERE s.sku_code = :sku AND p.status IN ('aprovado', 'enviado', 'recebido_parcial')
                    """
                ),
                {"sku": sku_code},
            )
        ]


def test_tapete_marrom_vendia_10_por_dia_e_parou_com_estoque() -> None:
    janela, venda_diaria = _janela_e_lambda(_vendas_por_dia()[TAPETE_MARROM])

    assert 9 <= venda_diaria <= 11
    assert janela == [5, 0]
    assert _cobertura_dias(TAPETE_MARROM) > 30


def test_tapete_banheiro_tem_5_cores_e_o_marrom_vende_muito_mais_que_o_branco() -> None:
    with get_engine().connect() as conn:
        linhas = conn.execute(
            text(
                """
                SELECT s.sku_code, s.cor, p.categoria, COALESCE(sum(v.quantidade), 0) AS qtd
                FROM erp.skus s JOIN erp.produtos p ON p.id = s.produto_id
                LEFT JOIN erp.vendas v ON v.sku_id = s.id AND v.data >= :inicio
                WHERE p.nome = 'Tapete Banheiro'
                GROUP BY 1, 2, 3
                """
            ),
            {"inicio": INICIO_DIARIO},
        ).all()

    assert len({linha.cor for linha in linhas}) == 5
    assert {linha.categoria for linha in linhas} == {"banho"}
    total = sum(linha.qtd for linha in linhas)
    participacao = {linha.sku_code: linha.qtd / total for linha in linhas}
    assert 0.40 <= participacao[TAPETE_MARROM] <= 0.50
    assert 0.05 <= participacao[TAPETE_BRANCO] <= 0.11
    assert all(_disponivel(linha.sku_code) > 0 for linha in linhas)


def test_sku_em_ruptura_sem_pedido_tem_a_katrina_como_fornecedor_mais_barato() -> None:
    assert 0 < _cobertura_dias(RUPTURA_SEM_PEDIDO) < 20
    assert _em_pedido_aberto(RUPTURA_SEM_PEDIDO) == []
    (mais_barato,) = _fetch_one(
        f"""
        SELECT f.nome FROM erp.fornecedores_skus fs
        JOIN erp.fornecedores f ON f.id = fs.fornecedor_id
        JOIN erp.skus s ON s.id = fs.sku_id
        WHERE s.sku_code = '{RUPTURA_SEM_PEDIDO}'
        ORDER BY fs.preco_unitario_atual LIMIT 1
        """
    )
    assert mais_barato == "Katrina Têxtil"


def test_pedido_enviado_com_data_vencida_ha_10_dias_tem_um_sku_em_ruptura() -> None:
    [(status, fornecedor, data_prevista, pendente)] = _em_pedido_aberto(RUPTURA_COM_PEDIDO_ATRASADO)

    assert (status, fornecedor, data_prevista) == ("enviado", "Katrina Têxtil", HOJE - timedelta(days=10))
    assert pendente > 0
    assert 0 < _cobertura_dias(RUPTURA_COM_PEDIDO_ATRASADO) < 20
    (atrasados,) = _fetch_one(
        f"""
        SELECT count(*) FROM erp.pedidos_compra
        WHERE status IN ('aprovado', 'enviado', 'recebido_parcial') AND data_prevista_entrega < '{HOJE}'
        """
    )
    assert atrasados == 1


def test_sku_que_parou_de_vender_sem_estoque() -> None:
    janela, venda_diaria = _janela_e_lambda(_vendas_por_dia()[QUEDA_SEM_ESTOQUE])

    assert venda_diaria >= 1
    assert janela == [0, 0]
    assert _disponivel(QUEDA_SEM_ESTOQUE) == 0


def test_so_os_cenarios_pararam_de_vender() -> None:
    pararam = set()
    for sku_code, vendas in _vendas_por_dia().items():
        janela, venda_diaria = _janela_e_lambda(vendas)
        if venda_diaria >= 1 and _poisson_ate(sum(janela), venda_diaria * 2) < 0.01:
            pararam.add(sku_code)

    assert pararam == {TAPETE_MARROM, QUEDA_SEM_ESTOQUE}


def test_setores_de_exemplo_e_o_setor_dos_cenarios() -> None:
    with get_engine().connect() as conn:
        nomes = set(conn.execute(text("SELECT nome FROM copilot.setores WHERE ativo")).scalars())
        linhas = conn.execute(
            text("SELECT ss.sku_code, s.nome FROM copilot.setores_sku ss JOIN copilot.setores s ON s.id = ss.setor_id")
        ).all()
    setor_de: dict[str, str] = {linha.sku_code: linha.nome for linha in linhas}

    assert {"Banho", "Cama", "Mesa", "Cozinha", "Tapetes"} <= nomes
    assert setor_de[TAPETE_MARROM] == "Tapetes"
    assert setor_de[TAPETE_BRANCO] == "Tapetes"
    assert setor_de[RUPTURA_SEM_PEDIDO] == "Cama"
    assert setor_de[QUEDA_SEM_ESTOQUE] == "Cozinha"


def test_skus_sinteticos_a_mais() -> None:
    (antes,) = _fetch_one("SELECT count(*) FROM erp.skus")
    try:
        run_seed(skus_extras=12)
        (depois,) = _fetch_one("SELECT count(*) FROM erp.skus")
        (sinteticos_com_venda,) = _fetch_one(
            """
            SELECT count(DISTINCT s.id) FROM erp.skus s
            JOIN erp.vendas v ON v.sku_id = s.id
            JOIN erp.estoque_snapshot e ON e.sku_id = s.id
            WHERE s.sku_code LIKE 'SINT%'
            """
        )
        assert depois == antes + 12
        assert sinteticos_com_venda == 12
    finally:
        run_seed()


def test_idempotencia_reseed() -> None:
    # Rodar o seed uma segunda vez deve deixar o banco no mesmo estado.
    (skus_antes,) = _fetch_one("SELECT count(*) FROM erp.skus")
    (mov_antes,) = _fetch_one("SELECT count(*) FROM erp.movimentacoes_estoque")
    (hash_antes,) = _fetch_one(
        "SELECT md5(string_agg(sku_code, ',' ORDER BY sku_code)) FROM erp.skus"
    )
    (vendas_antes,) = _fetch_one(_HASH_DAS_VENDAS)

    run_seed()

    (skus_depois,) = _fetch_one("SELECT count(*) FROM erp.skus")
    (mov_depois,) = _fetch_one("SELECT count(*) FROM erp.movimentacoes_estoque")
    (hash_depois,) = _fetch_one(
        "SELECT md5(string_agg(sku_code, ',' ORDER BY sku_code)) FROM erp.skus"
    )
    (vendas_depois,) = _fetch_one(_HASH_DAS_VENDAS)

    assert skus_antes == skus_depois
    assert mov_antes == mov_depois
    assert hash_antes == hash_depois
    assert vendas_antes == vendas_depois


_HASH_DAS_VENDAS = """
    SELECT md5(string_agg(id::text || data::text || quantidade::text, ',' ORDER BY id))
    FROM erp.vendas
"""
