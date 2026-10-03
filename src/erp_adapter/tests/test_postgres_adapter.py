"""Testes de integração do `PostgresERPAdapter` contra Postgres real.

Requerem `docker compose up` + `alembic upgrade head` + seed populado.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from sqlalchemy import text

from scripts.seed import run as run_seed
from src.db.engine import get_engine
from src.erp_adapter.postgres import PostgresERPAdapter
from src.inventory.schemas import STATUS_EM_TRANSITO
from tests.fakes import uid


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


_FORNECEDOR_INATIVO = uid("fornecedor", "teste-inativo")
_FORNECEDOR_VINCULO_INATIVO = uid("fornecedor", "teste-vinculo-inativo")
_SKU_INATIVO_CODE = "TESTE-SKU-INATIVO"


@pytest.fixture
def inativos() -> Iterator[str]:
    """Pendura no primeiro SKU dois fornecedores baratíssimos mas cortáveis
    (fornecedor inativo; vínculo inativo) e cria um SKU inativo. Devolve o
    `sku_code` que recebeu os vínculos."""
    code = _algum_sku_code()
    agora = datetime.now(UTC)
    with get_engine().begin() as conn:
        (sku_id, produto_id) = conn.execute(
            text("SELECT id, produto_id FROM erp.skus WHERE sku_code = :c"),
            {"c": code},
        ).one()
        for fornecedor_id, nome, fornecedor_ativo, vinculo_ativo in [
            (_FORNECEDOR_INATIVO, "Teste Inativo", False, True),
            (_FORNECEDOR_VINCULO_INATIVO, "Teste Vínculo Inativo", True, False),
        ]:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.fornecedores
                      (id, nome, cnpj, prazo_pagamento_padrao, pedido_minimo_reais,
                       lead_time_dias_contratado, ativo, criado_em)
                    VALUES (:id, :nome, '00.000.000/0001-00', '30', 0, 1, :ativo,
                            :agora)
                    """
                ),
                {
                    "id": fornecedor_id,
                    "nome": nome,
                    "ativo": fornecedor_ativo,
                    "agora": agora,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO erp.fornecedores_skus
                      (fornecedor_id, sku_id, preco_unitario_atual, moq_unidades,
                       lead_time_dias_observado, ativo, atualizado_em)
                    VALUES (:fornecedor_id, :sku_id, 1, 1, NULL, :ativo, :agora)
                    """
                ),
                {
                    "fornecedor_id": fornecedor_id,
                    "sku_id": sku_id,
                    "ativo": vinculo_ativo,
                    "agora": agora,
                },
            )
        conn.execute(
            text(
                """
                INSERT INTO erp.skus
                  (id, produto_id, sku_code, cor, tamanho, gramatura, material,
                   ativo, criado_em)
                VALUES (:id, :produto_id, :code, 'branco', '70x140', NULL, NULL,
                        FALSE, :agora)
                """
            ),
            {
                "id": uid("sku", _SKU_INATIVO_CODE),
                "produto_id": produto_id,
                "code": _SKU_INATIVO_CODE,
                "agora": agora,
            },
        )
    try:
        yield code
    finally:
        with get_engine().begin() as conn:
            ids = {"a": _FORNECEDOR_INATIVO, "b": _FORNECEDOR_VINCULO_INATIVO}
            conn.execute(
                text("DELETE FROM erp.fornecedores_skus WHERE fornecedor_id IN (:a, :b)"),
                ids,
            )
            conn.execute(
                text("DELETE FROM erp.fornecedores WHERE id IN (:a, :b)"), ids
            )
            conn.execute(
                text("DELETE FROM erp.skus WHERE sku_code = :c"),
                {"c": _SKU_INATIVO_CODE},
            )


def test_carregar_sku(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()

    sku = adapter.carregar_sku(code)

    assert sku is not None
    assert sku.sku_code == code
    assert sku.produto_nome
    assert sku.categoria in {"felpudo", "jogo_cama", "mesa", "cozinha"}


def test_carregar_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.carregar_sku("NAO-EXISTE-XYZ") is None


def test_listar_skus(adapter: PostgresERPAdapter) -> None:
    skus = adapter.listar_skus()

    assert 70 <= len(skus) <= 90
    codes = [s.sku_code for s in skus]
    assert codes == sorted(codes)
    assert all(s.ativo for s in skus)


def test_listar_skus_corta_inativos(
    adapter: PostgresERPAdapter, inativos: str
) -> None:
    codes = {s.sku_code for s in adapter.listar_skus()}

    assert _SKU_INATIVO_CODE not in codes


def test_carregar_fornecedor(adapter: PostgresERPAdapter) -> None:
    fornecedores = adapter.fornecedores_de(_algum_sku_code())
    assert fornecedores

    fornecedor = adapter.carregar_fornecedor(fornecedores[0].fornecedor_id)

    assert fornecedor is not None
    assert fornecedor.nome == fornecedores[0].fornecedor_nome
    assert fornecedor.cnpj
    assert fornecedor.ativo is True


def test_carregar_fornecedor_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.carregar_fornecedor(UUID(int=0)) is None


def test_fornecedores_de_ordena_por_preco(adapter: PostgresERPAdapter) -> None:
    fornecedores = adapter.fornecedores_de(_algum_sku_code())

    assert fornecedores, "SKU do seed deve ter fornecedores"
    precos = [f.preco_unitario_reais for f in fornecedores]
    assert precos == sorted(precos)
    assert all(f.fornecedor_nome for f in fornecedores)


def test_fornecedores_de_corta_inativos(
    adapter: PostgresERPAdapter, inativos: str
) -> None:
    ids = {f.fornecedor_id for f in adapter.fornecedores_de(inativos)}

    assert ids, "fornecedores ativos do seed continuam aparecendo"
    assert _FORNECEDOR_INATIVO not in ids
    assert _FORNECEDOR_VINCULO_INATIVO not in ids


def test_fornecedores_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.fornecedores_de("NAO-EXISTE-XYZ") == []


def test_estoque_de(adapter: PostgresERPAdapter) -> None:
    estoque = adapter.estoque_de(_algum_sku_code())

    assert estoque is not None
    assert estoque.quantidade_disponivel >= 0
    assert estoque.quantidade_reservada >= 0


def test_estoque_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.estoque_de("NAO-EXISTE-XYZ") is None


def test_vendas_de(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.carregar_sku(code)
    assert sku is not None
    desde = datetime(2024, 1, 1, tzinfo=UTC)

    vendas = adapter.vendas_de(code, desde)

    assert vendas, "seed deve gerar vendas para todo SKU"
    assert all(v.sku_id == sku.id for v in vendas)
    assert all(v.data >= desde for v in vendas)
    datas = [v.data for v in vendas]
    assert datas == sorted(datas)


def test_vendas_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.vendas_de("NAO-EXISTE-XYZ", datetime(2020, 1, 1, tzinfo=UTC)) == []


def test_movimentacoes_de(adapter: PostgresERPAdapter) -> None:
    code = _algum_sku_code()
    sku = adapter.carregar_sku(code)
    assert sku is not None
    desde = datetime(2024, 1, 1, tzinfo=UTC)

    movs = adapter.movimentacoes_de(code, desde)

    assert movs, "seed deve gerar movimentações para todo SKU"
    assert all(m.sku_id == sku.id for m in movs)
    assert all(m.data >= desde for m in movs)
    datas = [m.data for m in movs]
    assert datas == sorted(datas)


def test_movimentacoes_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert (
        adapter.movimentacoes_de("NAO-EXISTE-XYZ", datetime(2020, 1, 1, tzinfo=UTC))
        == []
    )


_SKU_TRANSITO_CODE = "TESTE-SKU-TRANSITO"


def _pedido_id(status: str) -> UUID:
    return uid("pedido", f"teste-transito|{status}")


_PEDIDOS_TESTE_TRANSITO = [
    ("rascunho", 0, None),
    ("aprovado", 0, None),
    ("enviado", 0, date(2026, 11, 10)),
    ("recebido_parcial", 40, date(2026, 10, 5)),
    ("recebido_total", 100, None),
    ("cancelado", 0, None),
]


@pytest.fixture
def fornecedor_com_pedidos_em_transito() -> Iterator[UUID]:
    """Cria um SKU sem histórico e pendura nele um pedido de cada status,
    todos com 100 unidades. O `recebido_parcial` já recebeu 40, e um
    segundo item dele (em outro SKU) não deve vazar. Devolve o id do
    fornecedor dos pedidos."""
    agora = datetime.now(UTC)
    with get_engine().begin() as conn:
        (outro_sku_id, produto_id) = conn.execute(
            text("SELECT id, produto_id FROM erp.skus WHERE sku_code = :c"),
            {"c": _algum_sku_code()},
        ).one()
        (fornecedor_id,) = conn.execute(
            text("SELECT id FROM erp.fornecedores ORDER BY nome LIMIT 1")
        ).one()
        sku_id = uid("sku", _SKU_TRANSITO_CODE)
        conn.execute(
            text(
                """
                INSERT INTO erp.skus
                  (id, produto_id, sku_code, cor, tamanho, gramatura, material,
                   ativo, criado_em)
                VALUES (:id, :produto_id, :code, 'branco', '70x140', NULL, NULL,
                        TRUE, :agora)
                """
            ),
            {
                "id": sku_id,
                "produto_id": produto_id,
                "code": _SKU_TRANSITO_CODE,
                "agora": agora,
            },
        )
        for status, recebida, previsao in _PEDIDOS_TESTE_TRANSITO:
            pedido_id = _pedido_id(status)
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra
                      (id, fornecedor_id, status, data_prevista_entrega,
                       valor_total_reais)
                    VALUES (:id, :fornecedor_id, :status, :previsao, 0)
                    """
                ),
                {
                    "id": pedido_id,
                    "fornecedor_id": fornecedor_id,
                    "status": status,
                    "previsao": previsao,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra_itens
                      (id, pedido_id, sku_id, quantidade, preco_unitario_reais,
                       quantidade_recebida)
                    VALUES (:id, :pedido_id, :sku_id, 100, 1, :recebida)
                    """
                ),
                {
                    "id": uid("pedido_item", f"{pedido_id}|0"),
                    "pedido_id": pedido_id,
                    "sku_id": sku_id,
                    "recebida": recebida,
                },
            )
        conn.execute(
            text(
                """
                INSERT INTO erp.pedidos_compra_itens
                  (id, pedido_id, sku_id, quantidade, preco_unitario_reais,
                   quantidade_recebida)
                VALUES (:id, :pedido_id, :sku_id, 999, 1, 0)
                """
            ),
            {
                "id": uid("pedido_item", "teste-transito|outro-sku"),
                "pedido_id": _pedido_id("recebido_parcial"),
                "sku_id": outro_sku_id,
            },
        )
    try:
        yield fornecedor_id
    finally:
        with get_engine().begin() as conn:
            conn.execute(
                text("DELETE FROM erp.pedidos_compra WHERE id = ANY(:ids)"),
                {"ids": [_pedido_id(s) for s, _, _ in _PEDIDOS_TESTE_TRANSITO]},
            )
            conn.execute(
                text("DELETE FROM erp.skus WHERE sku_code = :c"),
                {"c": _SKU_TRANSITO_CODE},
            )


def test_itens_em_transito_de_filtra_status_e_pendente(
    adapter: PostgresERPAdapter, fornecedor_com_pedidos_em_transito: UUID
) -> None:
    itens = adapter.itens_em_transito_de(_SKU_TRANSITO_CODE)

    assert [(i.status, i.quantidade_pendente) for i in itens] == [
        ("recebido_parcial", 60),
        ("enviado", 100),
        ("aprovado", 100),
    ]
    assert [i.pedido_id for i in itens] == [
        _pedido_id("recebido_parcial"),
        _pedido_id("enviado"),
        _pedido_id("aprovado"),
    ]
    assert [i.data_prevista_entrega for i in itens] == [
        date(2026, 10, 5),
        date(2026, 11, 10),
        None,
    ]
    assert all(i.fornecedor_id == fornecedor_com_pedidos_em_transito for i in itens)


def test_itens_em_transito_de_contra_o_seed(adapter: PostgresERPAdapter) -> None:
    with get_engine().connect() as conn:
        codes = conn.execute(
            text(
                """
                SELECT DISTINCT s.sku_code
                FROM erp.pedidos_compra_itens i
                JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                JOIN erp.skus s ON s.id = i.sku_id
                WHERE p.status::text = ANY(:status)
                """
            ),
            {"status": list(STATUS_EM_TRANSITO)},
        ).scalars().all()
    assert codes, "seed deve ter pedidos aprovado, enviado e recebido_parcial"

    itens = [i for code in codes for i in adapter.itens_em_transito_de(code)]

    assert {i.status for i in itens} == set(STATUS_EM_TRANSITO)
    assert all(i.quantidade_pendente > 0 for i in itens)


def test_itens_em_transito_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.itens_em_transito_de("NAO-EXISTE-XYZ") == []


def test_itens_de_pedido_de_contra_o_seed(adapter: PostgresERPAdapter) -> None:
    with get_engine().connect() as conn:
        code, quantos = conn.execute(
            text(
                """
                SELECT s.sku_code, count(*)
                FROM erp.pedidos_compra_itens i JOIN erp.skus s ON s.id = i.sku_id
                GROUP BY s.sku_code ORDER BY count(*) DESC, s.sku_code LIMIT 1
                """
            )
        ).one()

    itens = adapter.itens_de_pedido_de(code)

    assert len(itens) == quantos
    assert [i.criado_em for i in itens] == sorted((i.criado_em for i in itens), reverse=True)
    assert all(i.fornecedor_nome and i.preco_unitario_centavos > 0 and i.quantidade > 0 for i in itens)


def test_itens_de_pedido_de_traz_todos_os_status(
    adapter: PostgresERPAdapter, fornecedor_com_pedidos_em_transito: UUID
) -> None:
    itens = adapter.itens_de_pedido_de(_SKU_TRANSITO_CODE)

    assert {i.status for i in itens} == {s for s, _, _ in _PEDIDOS_TESTE_TRANSITO}
    assert all(i.fornecedor_id == fornecedor_com_pedidos_em_transito for i in itens)


def test_itens_de_pedido_de_sku_inexistente(adapter: PostgresERPAdapter) -> None:
    assert adapter.itens_de_pedido_de("NAO-EXISTE-XYZ") == []
