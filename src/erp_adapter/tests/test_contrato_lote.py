"""Contrato das leituras em lote do `ERPAdapter`, o retrato do estoque inteiro.

Roda contra o `InMemoryERPAdapter` e o `PostgresERPAdapter` com os mesmos dados. No
Postgres os dados entram ao lado do seed (códigos `LOTE-`), então as asserções olham só os
SKUs do teste. Requer `docker compose up` + `alembic upgrade head` e é pulado sem banco.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text

from src.db.engine import get_engine
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.postgres import PostgresERPAdapter
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
            conn.execute(text("SELECT 1 FROM erp.skus LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(not _db_disponivel(), reason="Postgres com schema erp precisa estar disponível")

PRODUTO = "Toalha Contrato Lote"
VENDENDO = make_sku("LOTE-VEND-01", produto_nome=PRODUTO, cor="azul")
PARADO = make_sku("LOTE-PARA-01", produto_nome=PRODUTO, cor="verde")
SEM_ESTOQUE = make_sku("LOTE-SEMS-01", produto_nome=PRODUTO, cor="rosa")
INATIVO = make_sku("LOTE-INAT-01", produto_nome=PRODUTO, cor="preto", ativo=False)
DO_TESTE = {s.sku_code for s in (VENDENDO, PARADO, SEM_ESTOQUE, INATIVO)}

CARO = make_fornecedor("Lote Caro Têxtil", lead_time_dias_contratado=30)
BARATO = make_fornecedor("Lote Barato Têxtil", lead_time_dias_contratado=45)
FECHADO = make_fornecedor("Lote Fechado Têxtil", ativo=False)


def _utc(*partes: int) -> datetime:
    return datetime(*partes, tzinfo=UTC)


def _montar() -> InMemoryERPAdapter:
    enviado = make_pedido_compra(CARO, "enviado", key="lote-enviado", data_prevista_entrega=date(2026, 10, 5))
    aprovado = make_pedido_compra(BARATO, "aprovado", key="lote-aprovado")
    recebido = make_pedido_compra(CARO, "recebido_total", key="lote-recebido")
    rascunho = make_pedido_compra(CARO, "rascunho", key="lote-rascunho")
    tardio = make_pedido_compra(BARATO, "enviado", key="lote-tardio", data_prevista_entrega=date(2026, 11, 1))
    return InMemoryERPAdapter(
        skus=[VENDENDO, PARADO, SEM_ESTOQUE, INATIVO],
        fornecedores=[CARO, BARATO, FECHADO],
        fornecedores_por_sku={
            VENDENDO.sku_code: [
                make_fornecedor_sku(CARO, preco_unitario_reais=2000, moq_unidades=48, lead_time_dias_observado=40),
                make_fornecedor_sku(BARATO, preco_unitario_reais=1500, moq_unidades=24, lead_time_dias_observado=None),
                make_fornecedor_sku(FECHADO, preco_unitario_reais=900),
            ],
            SEM_ESTOQUE.sku_code: [make_fornecedor_sku(FECHADO, preco_unitario_reais=900)],
            INATIVO.sku_code: [make_fornecedor_sku(CARO)],
        },
        estoques={
            VENDENDO.sku_code: make_estoque(disponivel=30, reservada=2),
            PARADO.sku_code: make_estoque(disponivel=0),
            INATIVO.sku_code: make_estoque(disponivel=7),
        },
        vendas=[
            make_venda(VENDENDO, _utc(2026, 7, 3, 10), 5),
            make_venda(VENDENDO, _utc(2026, 7, 20, 15), 7),
            make_venda(VENDENDO, _utc(2026, 8, 1, 0), 2),
            make_venda(VENDENDO, _utc(2026, 8, 31, 23, 30), 1),
            make_venda(VENDENDO, _utc(2026, 9, 2, 9), 3),
            make_venda(VENDENDO, _utc(2026, 9, 2, 17), 4),
            make_venda(SEM_ESTOQUE, _utc(2026, 9, 1, 12), 6),
            make_venda(INATIVO, _utc(2026, 9, 2, 12), 9),
        ],
        pedidos_compra=[enviado, aprovado, recebido, rascunho, tardio],
        itens_pedido_compra=[
            make_item_pedido_compra(tardio, VENDENDO, quantidade=10),
            make_item_pedido_compra(aprovado, VENDENDO, quantidade=20),
            make_item_pedido_compra(enviado, VENDENDO, quantidade=100, quantidade_recebida=40),
            make_item_pedido_compra(recebido, VENDENDO, quantidade=50, quantidade_recebida=50),
            make_item_pedido_compra(rascunho, VENDENDO, quantidade=30),
            make_item_pedido_compra(enviado, SEM_ESTOQUE, quantidade=12),
            make_item_pedido_compra(enviado, INATIVO, quantidade=5),
        ],
    )


@pytest.fixture
def postgres() -> Iterator[PostgresERPAdapter]:
    with erp_no_banco(_montar()):
        yield PostgresERPAdapter(get_engine())


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def erp(request: pytest.FixtureRequest) -> ERPAdapter:
    if request.param == "memoria":
        return _montar()
    return request.getfixturevalue("postgres")


def _do_teste[T](por_sku: dict[str, T]) -> dict[str, T]:
    return {codigo: valor for codigo, valor in por_sku.items() if codigo in DO_TESTE}


def test_estoques_traz_o_disponivel_dos_skus_ativos_com_estoque(erp: ERPAdapter) -> None:
    estoques = _do_teste(erp.estoques())

    assert {codigo: e.quantidade_disponivel for codigo, e in estoques.items()} == {
        VENDENDO.sku_code: 30,
        PARADO.sku_code: 0,
    }
    assert estoques[VENDENDO.sku_code].quantidade_reservada == 2


def test_giros_soma_as_vendas_por_sku_e_mes_desde_a_data(erp: ERPAdapter) -> None:
    giros = _do_teste(erp.giros(_utc(2026, 7, 10)))

    assert {codigo: [(m.ano, m.mes, m.quantidade) for m in meses] for codigo, meses in giros.items()} == {
        VENDENDO.sku_code: [(2026, 7, 7), (2026, 8, 3), (2026, 9, 7)],
        SEM_ESTOQUE.sku_code: [(2026, 9, 6)],
    }


def test_giros_guarda_a_primeira_venda_de_cada_mes(erp: ERPAdapter) -> None:
    meses = erp.giros(_utc(2026, 1, 1))[VENDENDO.sku_code]

    assert [m.primeira_venda for m in meses] == [_utc(2026, 7, 3, 10), _utc(2026, 8, 1, 0), _utc(2026, 9, 2, 9)]


def test_vendas_diarias_soma_por_sku_e_dia_em_utc(erp: ERPAdapter) -> None:
    diarias = _do_teste(erp.vendas_diarias(_utc(2026, 8, 31)))

    assert {codigo: [(d.dia, d.quantidade) for d in dias] for codigo, dias in diarias.items()} == {
        VENDENDO.sku_code: [(date(2026, 8, 31), 1), (date(2026, 9, 2), 7)],
        SEM_ESTOQUE.sku_code: [(date(2026, 9, 1), 6)],
    }


def test_fornecedores_por_sku_so_os_ativos_do_mais_barato_ao_mais_caro(erp: ERPAdapter) -> None:
    fornecedores = _do_teste(erp.fornecedores_por_sku())

    assert {codigo: [f.fornecedor_nome for f in lista] for codigo, lista in fornecedores.items()} == {
        VENDENDO.sku_code: [BARATO.nome, CARO.nome],
    }
    barato, caro = fornecedores[VENDENDO.sku_code]
    assert (barato.moq_unidades, barato.lead_time_dias_contratado, barato.lead_time_dias_observado) == (24, 45, None)
    assert (caro.preco_unitario_reais, caro.lead_time_dias_observado) == (2000, 40)


def test_itens_em_transito_dos_skus_ativos_pela_data_prevista(erp: ERPAdapter) -> None:
    itens = _do_teste(erp.itens_em_transito())

    assert {
        codigo: [(i.status, i.quantidade_pendente, i.data_prevista_entrega) for i in lista]
        for codigo, lista in itens.items()
    } == {
        VENDENDO.sku_code: [
            ("enviado", 60, date(2026, 10, 5)),
            ("enviado", 10, date(2026, 11, 1)),
            ("aprovado", 20, None),
        ],
        SEM_ESTOQUE.sku_code: [("enviado", 12, date(2026, 10, 5))],
    }


def test_leituras_em_lote_batem_com_as_leituras_por_sku(erp: ERPAdapter) -> None:
    estoques = erp.estoques()
    fornecedores = erp.fornecedores_por_sku()
    em_transito = erp.itens_em_transito()

    for codigo in DO_TESTE - {INATIVO.sku_code}:
        assert estoques.get(codigo) == erp.estoque_de(codigo)
        assert fornecedores.get(codigo, []) == erp.fornecedores_de(codigo)
        assert em_transito.get(codigo, []) == erp.itens_em_transito_de(codigo)
