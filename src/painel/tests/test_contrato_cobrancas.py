"""Contrato do `CobrancasRepositorio`.

Roda contra `InMemoryCobrancasRepositorio` e `PostgresCobrancasRepositorio`. O Postgres
requer `docker compose up` + `alembic upgrade head` e é pulado sem banco. Como `ultimas`
olha a tabela inteira, a fixture guarda as linhas existentes numa tabela temporária,
esvazia a tabela e devolve as linhas no teardown. Os check constraints da tabela são
conferidos só no Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db.engine import get_engine
from src.painel.in_memory import InMemoryCobrancasRepositorio
from src.painel.postgres import PostgresCobrancasRepositorio
from src.painel.repositorio import CobrancasRepositorio
from src.painel.schemas import CobrancaEntrega
from tests.autor_no_banco import AUTOR, autor_no_banco

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PEDIDO = UUID("00000000-0000-0000-0000-0000000000a1")
OUTRO_PEDIDO = UUID("00000000-0000-0000-0000-0000000000b2")
FORNECEDOR = UUID("00000000-0000-0000-0000-0000000000f1")


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.cobrancas_entrega LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.cobrancas_entrega precisa estar disponível"
)


@pytest.fixture
def postgres() -> Iterator[PostgresCobrancasRepositorio]:
    with autor_no_banco(), get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_cobrancas AS SELECT * FROM copilot.cobrancas_entrega"))
        conn.execute(text("DELETE FROM copilot.cobrancas_entrega"))
        conn.commit()
        try:
            yield PostgresCobrancasRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.cobrancas_entrega"))
            conn.execute(text("INSERT INTO copilot.cobrancas_entrega SELECT * FROM backup_cobrancas"))
            conn.execute(text("DROP TABLE backup_cobrancas"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def cobrancas(request: pytest.FixtureRequest) -> CobrancasRepositorio:
    if request.param == "memoria":
        return InMemoryCobrancasRepositorio()
    return request.getfixturevalue("postgres")


def cobranca(pedido_id: UUID = PEDIDO, *, minutos: int = 0, id: UUID | None = None, **campos: Any) -> CobrancaEntrega:
    padrao: dict[str, Any] = {
        "fornecedor_id": FORNECEDOR,
        "nova_previsao": None,
        "comentario": None,
        "cobrado_por": AUTOR.nome,
        "usuario_id": AUTOR.id,
    }
    return CobrancaEntrega(
        id=id or uuid4(),
        pedido_id=pedido_id,
        criado_em=INICIO + timedelta(minutes=minutos),
        **(padrao | campos),
    )


def test_gravar_e_listar_devolve_a_cobranca_igual(cobrancas: CobrancasRepositorio) -> None:
    gravadas = [
        cobranca(),
        cobranca(minutos=1, nova_previsao=date(2026, 10, 8), comentario="Caminhão parado na estrada."),
    ]
    for c in gravadas:
        cobrancas.gravar(c)

    assert cobrancas.listar(PEDIDO) == list(reversed(gravadas))


def test_listar_filtra_pelo_pedido(cobrancas: CobrancasRepositorio) -> None:
    do_pedido, do_outro = cobranca(PEDIDO), cobranca(OUTRO_PEDIDO)
    cobrancas.gravar(do_pedido)
    cobrancas.gravar(do_outro)

    assert cobrancas.listar(PEDIDO) == [do_pedido]
    assert cobrancas.listar(uuid4()) == []


def test_ultimas_traz_a_mais_recente_de_cada_pedido(cobrancas: CobrancasRepositorio) -> None:
    antiga, recente = cobranca(PEDIDO, minutos=0), cobranca(PEDIDO, minutos=10)
    outra = cobranca(OUTRO_PEDIDO, minutos=5)
    for c in (recente, antiga, outra):
        cobrancas.gravar(c)

    assert cobrancas.ultimas() == {PEDIDO: recente, OUTRO_PEDIDO: outra}


def test_mesma_hora_desempata_pelo_id(cobrancas: CobrancasRepositorio) -> None:
    menor = cobranca(id=UUID("00000000-0000-0000-0000-000000000001"))
    maior = cobranca(id=UUID("ffffffff-0000-0000-0000-000000000000"))
    cobrancas.gravar(menor)
    cobrancas.gravar(maior)

    assert cobrancas.listar(PEDIDO) == [maior, menor]
    assert cobrancas.ultimas() == {PEDIDO: maior}


def test_sem_cobranca_ultimas_e_vazio(cobrancas: CobrancasRepositorio) -> None:
    assert cobrancas.ultimas() == {}


@_sem_banco
def test_nome_de_quem_cobrou_nao_pode_ser_vazio(postgres: PostgresCobrancasRepositorio) -> None:
    with pytest.raises(IntegrityError):
        postgres.gravar(cobranca(cobrado_por=" "))
