"""Contrato da escrita de pedido de compra no `ERPAdapter`.

Roda contra `InMemoryERPAdapter` e `PostgresERPAdapter`. O port não tem
leitura de pedido, então cada cenário traz o próprio `ler_pedido`, que olha
as linhas gravadas. O Postgres requer `docker compose up` + `alembic upgrade
head` e é pulado sem banco; o cenário cria um fornecedor e um SKU próprios e
apaga tudo no teardown.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.db.engine import get_engine
from src.erp_adapter.in_memory import InMemoryERPAdapter, StatusPedidoCompra
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.postgres import PostgresERPAdapter
from src.purchasing.schemas import ItemNovoPedido
from tests.fakes import make_fornecedor, make_pedido_compra, make_sku, uid


@dataclass(frozen=True)
class PedidoGravado:
    fornecedor_id: UUID
    status: str
    aprovado_em: datetime | None
    data_prevista_entrega: date | None
    valor_total_centavos: int
    observacao: str | None
    itens: list[tuple[str, int, int, int]]


@dataclass(frozen=True)
class Cenario:
    adapter: ERPAdapter
    fornecedor_id: UUID
    sku_codes: tuple[str, str]
    ler_pedido: Callable[[UUID], PedidoGravado | None]
    inserir_pedido: Callable[[StatusPedidoCompra], None]


def _cenario_em_memoria() -> Cenario:
    skus = [make_sku("CONTRATO-A"), make_sku("CONTRATO-B")]
    fornecedor = make_fornecedor("Contrato Têxtil")
    adapter = InMemoryERPAdapter(skus=skus, fornecedores=[fornecedor])
    codigos = {s.id: s.sku_code for s in skus}

    def ler_pedido(pedido_id: UUID) -> PedidoGravado | None:
        pedido = next((p for p in adapter.pedidos_compra if p.id == pedido_id), None)
        if pedido is None:
            return None
        return PedidoGravado(
            fornecedor_id=pedido.fornecedor_id,
            status=pedido.status,
            aprovado_em=pedido.aprovado_em,
            data_prevista_entrega=pedido.data_prevista_entrega,
            valor_total_centavos=pedido.valor_total_centavos,
            observacao=pedido.observacao,
            itens=[
                (codigos[i.sku_id], i.quantidade, i.preco_unitario_centavos, i.quantidade_recebida)
                for i in adapter.itens_pedido_compra
                if i.pedido_id == pedido_id
            ],
        )

    def inserir_pedido(status: StatusPedidoCompra) -> None:
        adapter.pedidos_compra.append(make_pedido_compra(fornecedor, status, key=f"contrato|{status}"))

    return Cenario(adapter, fornecedor.id, ("CONTRATO-A", "CONTRATO-B"), ler_pedido, inserir_pedido)


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.produtos LIMIT 1")).one()
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com schema erp e produtos precisa estar disponível"
)

_FORNECEDOR_PG = uid("fornecedor", "teste-contrato-pedido")
_SKUS_PG = ("TESTE-CONTRATO-A", "TESTE-CONTRATO-B")


def _ler_pedido_postgres(pedido_id: UUID) -> PedidoGravado | None:
    with get_engine().connect() as conn:
        pedido = conn.execute(
            text(
                """
                SELECT fornecedor_id, status::text AS status, aprovado_em,
                       data_prevista_entrega, valor_total_reais, observacao
                FROM erp.pedidos_compra WHERE id = :id
                """
            ),
            {"id": pedido_id},
        ).one_or_none()
        if pedido is None:
            return None
        itens = conn.execute(
            text(
                """
                SELECT s.sku_code, i.quantidade, i.preco_unitario_reais, i.quantidade_recebida
                FROM erp.pedidos_compra_itens i JOIN erp.skus s ON s.id = i.sku_id
                WHERE i.pedido_id = :id
                ORDER BY s.sku_code
                """
            ),
            {"id": pedido_id},
        ).all()
    return PedidoGravado(
        fornecedor_id=pedido.fornecedor_id,
        status=pedido.status,
        aprovado_em=pedido.aprovado_em,
        data_prevista_entrega=pedido.data_prevista_entrega,
        valor_total_centavos=pedido.valor_total_reais,
        observacao=pedido.observacao,
        itens=[tuple(i) for i in itens],
    )


def _inserir_pedido_postgres(status: StatusPedidoCompra) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO erp.pedidos_compra (id, fornecedor_id, status, valor_total_reais)
                VALUES (:id, :fornecedor_id, :status, 0)
                """
            ),
            {"id": uuid4(), "fornecedor_id": _FORNECEDOR_PG, "status": status},
        )


@pytest.fixture
def postgres() -> Iterator[Cenario]:
    agora = datetime.now(UTC)
    with get_engine().begin() as conn:
        (produto_id,) = conn.execute(text("SELECT id FROM erp.produtos LIMIT 1")).one()
        conn.execute(
            text(
                """
                INSERT INTO erp.fornecedores
                  (id, nome, cnpj, prazo_pagamento_padrao, pedido_minimo_reais,
                   lead_time_dias_contratado, ativo, criado_em)
                VALUES (:id, 'Teste Contrato Pedido', '00.000.000/0001-00', '30', 0, 30,
                        TRUE, :agora)
                """
            ),
            {"id": _FORNECEDOR_PG, "agora": agora},
        )
        for code in _SKUS_PG:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.skus
                      (id, produto_id, sku_code, cor, tamanho, gramatura, material, ativo, criado_em)
                    VALUES (:id, :produto_id, :code, 'branco', '70x140', NULL, NULL, TRUE, :agora)
                    """
                ),
                {"id": uid("sku", code), "produto_id": produto_id, "code": code, "agora": agora},
            )
    try:
        yield Cenario(
            PostgresERPAdapter(get_engine()),
            _FORNECEDOR_PG,
            _SKUS_PG,
            _ler_pedido_postgres,
            _inserir_pedido_postgres,
        )
    finally:
        with get_engine().begin() as conn:
            conn.execute(
                text("DELETE FROM erp.pedidos_compra WHERE fornecedor_id = :id"),
                {"id": _FORNECEDOR_PG},
            )
            conn.execute(
                text("DELETE FROM erp.skus WHERE sku_code = ANY(:codes)"), {"codes": list(_SKUS_PG)}
            )
            conn.execute(text("DELETE FROM erp.fornecedores WHERE id = :id"), {"id": _FORNECEDOR_PG})


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def cenario(request: pytest.FixtureRequest) -> Cenario:
    if request.param == "memoria":
        return _cenario_em_memoria()
    return request.getfixturevalue("postgres")


PREVISTA = date(2026, 11, 20)


def _criar(cenario: Cenario, itens: list[ItemNovoPedido] | None = None) -> UUID:
    a, b = cenario.sku_codes
    return cenario.adapter.criar_pedido_compra(
        cenario.fornecedor_id,
        itens
        if itens is not None
        else [
            ItemNovoPedido(sku_code=a, quantidade=200, preco_unitario_centavos=1800),
            ItemNovoPedido(sku_code=b, quantidade=48, preco_unitario_centavos=2550),
        ],
        PREVISTA,
        "Criado pelo teste de contrato.",
    )


def test_criar_pedido_grava_pedido_aprovado_com_itens_e_valor_somado(cenario: Cenario) -> None:
    pedido_id = _criar(cenario)

    gravado = cenario.ler_pedido(pedido_id)
    assert gravado is not None
    assert gravado.fornecedor_id == cenario.fornecedor_id
    assert gravado.status == "aprovado"
    assert gravado.aprovado_em is not None
    assert abs(gravado.aprovado_em - datetime.now(UTC)) < timedelta(minutes=1)
    assert gravado.data_prevista_entrega == PREVISTA
    assert gravado.valor_total_centavos == 200 * 1800 + 48 * 2550
    assert gravado.observacao == "Criado pelo teste de contrato."
    a, b = cenario.sku_codes
    assert sorted(gravado.itens) == [(a, 200, 1800, 0), (b, 48, 2550, 0)]


def test_cada_pedido_criado_tem_id_proprio(cenario: Cenario) -> None:
    assert _criar(cenario) != _criar(cenario)


def test_pedido_criado_entra_em_transito(cenario: Cenario) -> None:
    pedido_id = _criar(cenario)

    itens = cenario.adapter.itens_em_transito_de(cenario.sku_codes[0])

    assert [(i.pedido_id, i.status, i.quantidade_pendente) for i in itens] == [
        (pedido_id, "aprovado", 200)
    ]
    assert itens[0].fornecedor_id == cenario.fornecedor_id
    assert itens[0].data_prevista_entrega == PREVISTA


def test_fornecedor_sem_pedido(cenario: Cenario) -> None:
    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is False


def test_fornecedor_passa_a_ter_pedido_depois_de_criar(cenario: Cenario) -> None:
    _criar(cenario)

    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is True


def test_rascunho_e_cancelado_nao_contam_como_pedido(cenario: Cenario) -> None:
    cenario.inserir_pedido("rascunho")
    cenario.inserir_pedido("cancelado")

    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is False


@pytest.mark.parametrize("status", ["enviado", "recebido_total"])
def test_outros_status_contam_como_pedido(cenario: Cenario, status: StatusPedidoCompra) -> None:
    cenario.inserir_pedido(status)

    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is True


def test_fornecedor_inexistente_nao_tem_pedido(cenario: Cenario) -> None:
    assert cenario.adapter.fornecedor_tem_pedido(UUID(int=0)) is False


def test_pedido_sem_itens_e_rejeitado(cenario: Cenario) -> None:
    with pytest.raises(ValueError):
        _criar(cenario, itens=[])

    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is False


def test_sku_inexistente_rejeita_o_pedido_inteiro(cenario: Cenario) -> None:
    itens = [
        ItemNovoPedido(sku_code=cenario.sku_codes[0], quantidade=10, preco_unitario_centavos=100),
        ItemNovoPedido(sku_code="NAO-EXISTE-XYZ", quantidade=10, preco_unitario_centavos=100),
    ]

    with pytest.raises(ValueError, match="NAO-EXISTE-XYZ"):
        _criar(cenario, itens=itens)

    assert cenario.adapter.fornecedor_tem_pedido(cenario.fornecedor_id) is False
    assert cenario.adapter.itens_em_transito_de(cenario.sku_codes[0]) == []


def test_fornecedor_inexistente_e_rejeitado(cenario: Cenario) -> None:
    item = ItemNovoPedido(sku_code=cenario.sku_codes[0], quantidade=10, preco_unitario_centavos=100)

    with pytest.raises(ValueError):
        cenario.adapter.criar_pedido_compra(UUID(int=0), [item], PREVISTA, "x")
