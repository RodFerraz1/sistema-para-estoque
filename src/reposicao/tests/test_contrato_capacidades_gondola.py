"""Contrato do `CapacidadesGondolaRepositorio`.

Roda contra as versões em memória e Postgres. O Postgres requer `docker compose up` +
`alembic upgrade head` e é pulado sem banco. Como `todas` olha a tabela inteira, a fixture
guarda as linhas existentes de `capacidades_gondola` numa tabela temporária, esvazia a tabela
e devolve as linhas no teardown. O check constraint é conferido só no Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db.engine import get_engine
from src.reposicao.in_memory import InMemoryCapacidadesGondolaRepositorio
from src.reposicao.postgres import PostgresCapacidadesGondolaRepositorio
from src.reposicao.repositorio import CapacidadesGondolaRepositorio
from src.reposicao.schemas import CapacidadeGondola
from tests.autor_no_banco import AUTOR, autor_no_banco

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TAPETE = UUID("00000000-0000-0000-0000-0000000aa001")
PANO = UUID("00000000-0000-0000-0000-0000000aa002")


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.capacidades_gondola LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.capacidades_gondola precisa estar disponível"
)


@pytest.fixture
def no_postgres() -> Iterator[CapacidadesGondolaRepositorio]:
    with autor_no_banco(), get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_capacidades AS SELECT * FROM copilot.capacidades_gondola"))
        conn.execute(text("DELETE FROM copilot.capacidades_gondola"))
        conn.commit()
        try:
            yield PostgresCapacidadesGondolaRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.capacidades_gondola"))
            conn.execute(text("INSERT INTO copilot.capacidades_gondola SELECT * FROM backup_capacidades"))
            conn.execute(text("DROP TABLE backup_capacidades"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def repositorio(request: pytest.FixtureRequest) -> CapacidadesGondolaRepositorio:
    if request.param == "memoria":
        return InMemoryCapacidadesGondolaRepositorio()
    return request.getfixturevalue("no_postgres")


def capacidade(produto_id: UUID, quantas: int, quando: datetime = INICIO) -> CapacidadeGondola:
    return CapacidadeGondola(produto_id=produto_id, capacidade=quantas, usuario_id=AUTOR.id, atualizado_em=quando)


def test_sem_capacidade_gravada(repositorio: CapacidadesGondolaRepositorio) -> None:
    assert repositorio.do_produto(TAPETE) is None
    assert repositorio.todas() == {}


def test_grava_e_le_a_capacidade_do_produto(repositorio: CapacidadesGondolaRepositorio) -> None:
    repositorio.gravar(capacidade(TAPETE, 12))

    assert repositorio.do_produto(TAPETE) == capacidade(TAPETE, 12)
    assert repositorio.do_produto(PANO) is None


def test_vale_a_ultima_gravada(repositorio: CapacidadesGondolaRepositorio) -> None:
    repositorio.gravar(capacidade(TAPETE, 12))
    repositorio.gravar(capacidade(TAPETE, 20, INICIO + timedelta(days=3)))

    assert repositorio.do_produto(TAPETE) == capacidade(TAPETE, 20, INICIO + timedelta(days=3))


def test_todas_pelo_produto(repositorio: CapacidadesGondolaRepositorio) -> None:
    repositorio.gravar(capacidade(TAPETE, 12))
    repositorio.gravar(capacidade(PANO, 6))

    assert repositorio.todas() == {TAPETE: capacidade(TAPETE, 12), PANO: capacidade(PANO, 6)}


@_sem_banco
def test_capacidade_zero_e_recusada_pelo_banco(no_postgres: CapacidadesGondolaRepositorio) -> None:
    with pytest.raises(IntegrityError):
        no_postgres.gravar(CapacidadeGondola.model_construct(
            produto_id=TAPETE, capacidade=0, usuario_id=AUTOR.id, atualizado_em=INICIO
        ))
