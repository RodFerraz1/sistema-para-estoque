"""Contrato do `AvisosRepositorio`.

Roda contra `InMemoryAvisosRepositorio` e `PostgresAvisosRepositorio`. O Postgres requer
`docker compose up` + `alembic upgrade head` e é pulado sem banco. Como `listar` sem SKU
olha a tabela inteira, a fixture guarda as linhas existentes numa tabela temporária,
esvazia a tabela e devolve as linhas no teardown.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.db.engine import get_engine
from src.painel.in_memory import InMemoryAvisosRepositorio
from src.painel.postgres import PostgresAvisosRepositorio
from src.painel.repositorio import AvisosRepositorio
from src.painel.schemas import Aviso
from tests.autor_no_banco import AUTOR, autor_no_banco

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.avisos LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.avisos precisa estar disponível"
)


@pytest.fixture
def postgres() -> Iterator[PostgresAvisosRepositorio]:
    with autor_no_banco(), get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_avisos AS SELECT * FROM copilot.avisos"))
        conn.execute(text("DELETE FROM copilot.avisos"))
        conn.commit()
        try:
            yield PostgresAvisosRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.avisos"))
            conn.execute(text("INSERT INTO copilot.avisos SELECT * FROM backup_avisos"))
            conn.execute(text("DROP TABLE backup_avisos"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def avisos(request: pytest.FixtureRequest) -> AvisosRepositorio:
    if request.param == "memoria":
        return InMemoryAvisosRepositorio()
    return request.getfixturevalue("postgres")


def aviso(
    sku_code: str = "TBC-BEGE-70140-01",
    *,
    minutos: int = 0,
    id: UUID | None = None,
    comentario: str | None = None,
    usuario_id: UUID | None = None,
) -> Aviso:
    return Aviso(
        id=id or uuid4(),
        sku_code=sku_code,
        tipo="acabou",
        comentario=comentario,
        avisado_por="Joana",
        usuario_id=usuario_id,
        criado_em=INICIO + timedelta(minutes=minutos),
    )


def test_gravar_e_listar_devolve_o_aviso_igual(avisos: AvisosRepositorio) -> None:
    gravado = aviso(comentario="Cliente X quer 200 peças.")

    avisos.gravar(gravado)

    assert avisos.listar(gravado.sku_code) == [gravado]


def test_listar_vem_do_mais_recente_para_o_mais_antigo(avisos: AvisosRepositorio) -> None:
    antigo, novo, meio = aviso(minutos=0), aviso(minutos=10), aviso(minutos=5)
    for a in (antigo, novo, meio):
        avisos.gravar(a)

    assert avisos.listar(antigo.sku_code) == [novo, meio, antigo]


def test_listar_por_sku_filtra_e_sem_sku_traz_todos(avisos: AvisosRepositorio) -> None:
    bege, branco = aviso("TBC-BEGE-70140-01"), aviso("TBC-BRAN-70140-01", minutos=1)
    avisos.gravar(bege)
    avisos.gravar(branco)

    assert avisos.listar("TBC-BEGE-70140-01") == [bege]
    assert avisos.listar("NAO-EXISTE") == []
    assert avisos.listar() == [branco, bege]


def test_mesma_hora_desempata_pelo_id(avisos: AvisosRepositorio) -> None:
    menor = aviso(id=UUID("00000000-0000-0000-0000-000000000001"))
    maior = aviso(id=UUID("ffffffff-0000-0000-0000-000000000000"))
    avisos.gravar(menor)
    avisos.gravar(maior)

    assert avisos.listar() == [maior, menor]


def test_autor_volta_igual_e_aviso_antigo_fica_sem_usuario(avisos: AvisosRepositorio) -> None:
    antigo, novo = aviso(minutos=0), aviso(minutos=1, usuario_id=AUTOR.id)
    avisos.gravar(antigo)
    avisos.gravar(novo)

    assert avisos.listar() == [novo, antigo]
