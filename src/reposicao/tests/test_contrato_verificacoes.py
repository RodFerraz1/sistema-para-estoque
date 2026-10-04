"""Contrato do `VerificacoesRepositorio`.

Roda contra `InMemoryVerificacoesRepositorio` e `PostgresVerificacoesRepositorio`. O
Postgres requer `docker compose up` + `alembic upgrade head` e é pulado sem banco. Como
`ultimas` olha a tabela inteira, a fixture guarda as linhas existentes numa tabela
temporária, esvazia a tabela e devolve as linhas no teardown. Os check constraints da
tabela são conferidos só no Postgres.
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
from src.reposicao.in_memory import InMemoryVerificacoesRepositorio
from src.reposicao.postgres import PostgresVerificacoesRepositorio
from src.reposicao.repositorio import VerificacoesRepositorio
from src.reposicao.schemas import VerificacaoGondola
from tests.autor_no_banco import AUTOR, autor_no_banco

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
SKU = "TAP-MARR-4060-01"
OUTRO_SKU = "TAP-CINZ-4060-02"


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.verificacoes_gondola LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.verificacoes_gondola precisa estar disponível"
)


@pytest.fixture
def postgres() -> Iterator[PostgresVerificacoesRepositorio]:
    with autor_no_banco(), get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_verificacoes AS SELECT * FROM copilot.verificacoes_gondola"))
        conn.execute(text("DELETE FROM copilot.verificacoes_gondola"))
        conn.commit()
        try:
            yield PostgresVerificacoesRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.verificacoes_gondola"))
            conn.execute(text("INSERT INTO copilot.verificacoes_gondola SELECT * FROM backup_verificacoes"))
            conn.execute(text("DROP TABLE backup_verificacoes"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def verificacoes(request: pytest.FixtureRequest) -> VerificacoesRepositorio:
    if request.param == "memoria":
        return InMemoryVerificacoesRepositorio()
    return request.getfixturevalue("postgres")


def verificacao(
    sku_code: str = SKU, *, minutos: int = 0, id: UUID | None = None, **campos: Any
) -> VerificacaoGondola:
    padrao: dict[str, Any] = {
        "resultado": "repus",
        "comentario": None,
        "disponivel_no_erp": 400,
        "verificado_por": AUTOR.nome,
        "usuario_id": AUTOR.id,
    }
    return VerificacaoGondola(
        id=id or uuid4(),
        sku_code=sku_code,
        criado_em=INICIO + timedelta(minutes=minutos),
        **(padrao | campos),
    )


def test_gravar_e_listar_devolve_a_verificacao_igual(verificacoes: VerificacoesRepositorio) -> None:
    gravadas = [
        verificacao(),
        verificacao(minutos=1, resultado="estava_na_gondola", comentario="Estava no lugar errado."),
        verificacao(minutos=2, resultado="sem_estoque_no_deposito", disponivel_no_erp=0),
    ]
    for v in gravadas:
        verificacoes.gravar(v)

    assert verificacoes.listar(SKU) == list(reversed(gravadas))


def test_listar_filtra_pelo_sku(verificacoes: VerificacoesRepositorio) -> None:
    do_sku, do_outro = verificacao(SKU), verificacao(OUTRO_SKU)
    verificacoes.gravar(do_sku)
    verificacoes.gravar(do_outro)

    assert verificacoes.listar(SKU) == [do_sku]
    assert verificacoes.listar("NAO-EXISTE") == []


def test_dos_skus_traz_as_dos_skus_a_partir_da_data(verificacoes: VerificacoesRepositorio) -> None:
    antiga, no_limite, recente = verificacao(SKU, minutos=-1), verificacao(SKU), verificacao(OUTRO_SKU, minutos=5)
    de_fora = verificacao("PM-AMAR-3040-01", minutos=6)
    for v in (recente, antiga, de_fora, no_limite):
        verificacoes.gravar(v)

    assert verificacoes.dos_skus({SKU, OUTRO_SKU}, INICIO) == [recente, no_limite]
    assert verificacoes.dos_skus(set(), INICIO) == []


def test_ultimas_traz_a_mais_recente_de_cada_sku(verificacoes: VerificacoesRepositorio) -> None:
    antiga, recente = verificacao(SKU, minutos=0), verificacao(SKU, minutos=10)
    outra = verificacao(OUTRO_SKU, minutos=5)
    for v in (recente, antiga, outra):
        verificacoes.gravar(v)

    assert verificacoes.ultimas() == {SKU: recente, OUTRO_SKU: outra}


def test_mesma_hora_desempata_pelo_id(verificacoes: VerificacoesRepositorio) -> None:
    menor = verificacao(id=UUID("00000000-0000-0000-0000-000000000001"))
    maior = verificacao(id=UUID("ffffffff-0000-0000-0000-000000000000"))
    verificacoes.gravar(menor)
    verificacoes.gravar(maior)

    assert verificacoes.listar(SKU) == [maior, menor]
    assert verificacoes.ultimas() == {SKU: maior}


def test_sem_verificacao_ultimas_e_vazio(verificacoes: VerificacoesRepositorio) -> None:
    assert verificacoes.ultimas() == {}


@_sem_banco
def test_nome_de_quem_verificou_nao_pode_ser_vazio(postgres: PostgresVerificacoesRepositorio) -> None:
    with pytest.raises(IntegrityError):
        postgres.gravar(verificacao(verificado_por=" "))


@_sem_banco
def test_resultado_fora_da_lista_nao_grava(postgres: PostgresVerificacoesRepositorio) -> None:
    with pytest.raises(IntegrityError):
        postgres.gravar(verificacao().model_copy(update={"resultado": "sumiu"}))
