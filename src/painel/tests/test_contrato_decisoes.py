"""Contrato do `DecisoesRepositorio`.

Roda contra `InMemoryDecisoesRepositorio` e `PostgresDecisoesRepositorio`. O Postgres
requer `docker compose up` + `alembic upgrade head` e é pulado sem banco. Como `ultimas`
olha a tabela inteira, a fixture guarda as linhas existentes numa tabela temporária,
esvazia a tabela e devolve as linhas no teardown. Os check constraints da tabela são
conferidos só no Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db.engine import get_engine
from src.painel.in_memory import InMemoryDecisoesRepositorio
from src.painel.postgres import PostgresDecisoesRepositorio
from src.painel.repositorio import DecisoesRepositorio
from src.painel.schemas import DecisaoCompra

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
BEGE = "TBC-BEGE-70140-01"
BRANCO = "TBC-BRAN-70140-01"


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.decisoes_compra LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.decisoes_compra precisa estar disponível"
)


@pytest.fixture
def postgres() -> Iterator[PostgresDecisoesRepositorio]:
    with get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_decisoes AS SELECT * FROM copilot.decisoes_compra"))
        conn.execute(text("DELETE FROM copilot.decisoes_compra"))
        conn.commit()
        try:
            yield PostgresDecisoesRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.decisoes_compra"))
            conn.execute(text("INSERT INTO copilot.decisoes_compra SELECT * FROM backup_decisoes"))
            conn.execute(text("DROP TABLE backup_decisoes"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def decisoes(request: pytest.FixtureRequest) -> DecisoesRepositorio:
    if request.param == "memoria":
        return InMemoryDecisoesRepositorio()
    return request.getfixturevalue("postgres")


def decisao(sku_code: str = BEGE, *, minutos: int = 0, id: UUID | None = None, **campos: Any) -> DecisaoCompra:
    padrao: dict[str, Any] = {
        "tipo": "vou_comprar",
        "quantidade": 300,
        "motivo": None,
        "comentario": None,
        "decidido_por": "Carlos",
        "quantidade_sugerida": 300,
        "politica_versao": 1,
    }
    return DecisaoCompra(
        id=id or uuid4(),
        sku_code=sku_code,
        criado_em=INICIO + timedelta(minutes=minutos),
        **(padrao | campos),
    )


def test_gravar_e_listar_devolve_a_decisao_igual(decisoes: DecisoesRepositorio) -> None:
    gravadas = [
        decisao(),
        decisao(minutos=1, tipo="negociando", quantidade=None, comentario="Volta sexta."),
        decisao(minutos=2, tipo="nao_comprar_agora", quantidade=None, motivo="Estoque alto.", quantidade_sugerida=0),
    ]
    for d in gravadas:
        decisoes.gravar(d)

    assert decisoes.listar(BEGE) == list(reversed(gravadas))


def test_listar_filtra_pelo_sku(decisoes: DecisoesRepositorio) -> None:
    bege, branco = decisao(BEGE), decisao(BRANCO)
    decisoes.gravar(bege)
    decisoes.gravar(branco)

    assert decisoes.listar(BEGE) == [bege]
    assert decisoes.listar("NAO-EXISTE") == []


def test_ultimas_traz_a_mais_recente_de_cada_sku(decisoes: DecisoesRepositorio) -> None:
    antiga, recente = decisao(BEGE, minutos=0), decisao(BEGE, minutos=10)
    branco = decisao(BRANCO, minutos=5)
    for d in (recente, antiga, branco):
        decisoes.gravar(d)

    assert decisoes.ultimas() == {BEGE: recente, BRANCO: branco}


def test_mesma_hora_desempata_pelo_id(decisoes: DecisoesRepositorio) -> None:
    menor = decisao(id=UUID("00000000-0000-0000-0000-000000000001"))
    maior = decisao(id=UUID("ffffffff-0000-0000-0000-000000000000"))
    decisoes.gravar(menor)
    decisoes.gravar(maior)

    assert decisoes.listar(BEGE) == [maior, menor]
    assert decisoes.ultimas() == {BEGE: maior}


def test_sem_decisao_ultimas_e_vazio(decisoes: DecisoesRepositorio) -> None:
    assert decisoes.ultimas() == {}


@_sem_banco
@pytest.mark.parametrize(
    "campos",
    [
        {"tipo": "vou_comprar", "quantidade": None},
        {"tipo": "vou_comprar", "quantidade": 0},
        {"tipo": "negociando", "quantidade": 10},
        {"tipo": "nao_comprar_agora", "quantidade": None, "motivo": None},
        {"tipo": "nao_comprar_agora", "quantidade": None, "motivo": "  "},
        {"decidido_por": " "},
    ],
    ids=[
        "comprar-sem-quantidade",
        "comprar-com-zero",
        "quantidade-fora-do-comprar",
        "nao-comprar-sem-motivo",
        "nao-comprar-com-motivo-em-branco",
        "sem-nome",
    ],
)
def test_check_constraints_espelham_as_validacoes(postgres: PostgresDecisoesRepositorio, campos: dict) -> None:
    with pytest.raises(IntegrityError):
        postgres.gravar(decisao(**campos))
