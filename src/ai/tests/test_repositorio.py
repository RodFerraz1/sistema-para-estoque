"""Contrato do `TrechosRepositorio`, com vetores feitos à mão.

Roda contra `InMemoryTrechosRepositorio` e `PostgresTrechosRepositorio`. O
Postgres requer `docker compose up` + `alembic upgrade head` e é pulado sem
banco. Como `buscar_similares` olha a tabela inteira, a fixture guarda os
trechos já ingeridos numa tabela temporária, esvazia a tabela e devolve os
trechos no teardown.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.ai.embeddings import DIMENSAO
from src.ai.in_memory import InMemoryTrechosRepositorio
from src.ai.postgres import PostgresTrechosRepositorio
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import TrechoIndexado
from src.db.engine import get_engine


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.trechos_corpus LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(),
    reason="Postgres com copilot.trechos_corpus precisa estar disponível",
)


@pytest.fixture
def postgres() -> Iterator[PostgresTrechosRepositorio]:
    with get_engine().connect() as conn:
        conn.execute(
            text("CREATE TEMP TABLE backup_trechos AS SELECT * FROM copilot.trechos_corpus")
        )
        conn.execute(text("DELETE FROM copilot.trechos_corpus"))
        conn.commit()
        try:
            yield PostgresTrechosRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.trechos_corpus"))
            conn.execute(text("INSERT INTO copilot.trechos_corpus SELECT * FROM backup_trechos"))
            conn.execute(text("DROP TABLE backup_trechos"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def repositorio(request: pytest.FixtureRequest) -> TrechosRepositorio:
    if request.param == "memoria":
        return InMemoryTrechosRepositorio()
    return request.getfixturevalue("postgres")


def vetor(*componentes: float) -> list[float]:
    return [*componentes, *[0.0] * (DIMENSAO - len(componentes))]


def trecho(id: str, embedding: list[float]) -> TrechoIndexado:
    documento = id.split("#")[0]
    return TrechoIndexado(
        id=id,
        documento=documento,
        titulo=f"Título de {id}",
        tipo="reuniao",
        data=date(2025, 3, 14),
        tags=["fornecedores", "sazonalidade"],
        texto=f"Texto de {id}",
        embedding=embedding,
    )


def test_busca_ordena_por_similaridade_de_cosseno(repositorio: TrechosRepositorio) -> None:
    repositorio.substituir_documento(
        "a.md",
        "h-a",
        [trecho("a.md#longe", vetor(0, 1)), trecho("a.md#perto", vetor(1, 0.1))],
    )
    repositorio.substituir_documento("b.md", "h-b", [trecho("b.md#igual", vetor(2, 0))])

    recuperados = repositorio.buscar_similares(vetor(1, 0), k=10)

    assert [t.id for t in recuperados] == ["b.md#igual", "a.md#perto", "a.md#longe"]
    assert recuperados[0].similaridade == pytest.approx(1.0)
    assert recuperados[1].similaridade == pytest.approx(1 / (1 + 0.1**2) ** 0.5)
    assert recuperados[2].similaridade == pytest.approx(0.0)


def test_busca_devolve_o_trecho_com_todos_os_campos(repositorio: TrechosRepositorio) -> None:
    original = trecho("a.md#secao", vetor(1))
    repositorio.substituir_documento("a.md", "h-a", [original])

    [recuperado] = repositorio.buscar_similares(vetor(1), k=1)

    assert recuperado.model_dump(exclude={"similaridade"}) == original.model_dump(
        exclude={"embedding"}
    )


def test_busca_respeita_k(repositorio: TrechosRepositorio) -> None:
    repositorio.substituir_documento(
        "a.md", "h-a", [trecho(f"a.md#s{i}", vetor(1, i)) for i in range(5)]
    )

    recuperados = repositorio.buscar_similares(vetor(1, 0), k=2)

    assert [t.id for t in recuperados] == ["a.md#s0", "a.md#s1"]


def test_busca_em_repositorio_vazio_devolve_lista_vazia(
    repositorio: TrechosRepositorio,
) -> None:
    assert repositorio.buscar_similares(vetor(1), k=5) == []


def test_hashes_por_documento(repositorio: TrechosRepositorio) -> None:
    repositorio.substituir_documento(
        "a.md", "h-a", [trecho("a.md#s1", vetor(1)), trecho("a.md#s2", vetor(0, 1))]
    )
    repositorio.substituir_documento("b.md", "h-b", [trecho("b.md#s1", vetor(1))])

    assert repositorio.hashes_por_documento() == {"a.md": "h-a", "b.md": "h-b"}


def test_substituir_troca_todos_os_trechos_do_documento_e_so_dele(
    repositorio: TrechosRepositorio,
) -> None:
    repositorio.substituir_documento(
        "a.md", "h-a", [trecho("a.md#velho", vetor(1)), trecho("a.md#fica", vetor(1))]
    )
    repositorio.substituir_documento("b.md", "h-b", [trecho("b.md#s1", vetor(1))])

    repositorio.substituir_documento(
        "a.md", "h-a2", [trecho("a.md#fica", vetor(1)), trecho("a.md#novo", vetor(1))]
    )

    ids = {t.id for t in repositorio.buscar_similares(vetor(1), k=10)}
    assert ids == {"a.md#fica", "a.md#novo", "b.md#s1"}
    assert repositorio.hashes_por_documento() == {"a.md": "h-a2", "b.md": "h-b"}


def test_remover_documento_apaga_os_trechos_dele(repositorio: TrechosRepositorio) -> None:
    repositorio.substituir_documento("a.md", "h-a", [trecho("a.md#s1", vetor(1))])
    repositorio.substituir_documento("b.md", "h-b", [trecho("b.md#s1", vetor(1))])

    repositorio.remover_documento("a.md")

    assert [t.id for t in repositorio.buscar_similares(vetor(1), k=10)] == ["b.md#s1"]
    assert repositorio.hashes_por_documento() == {"b.md": "h-b"}


def test_substituir_por_lista_vazia_tira_o_documento_do_indice(
    repositorio: TrechosRepositorio,
) -> None:
    repositorio.substituir_documento("a.md", "h-a", [trecho("a.md#s1", vetor(1))])

    repositorio.substituir_documento("a.md", "h-a2", [])

    assert repositorio.buscar_similares(vetor(1), k=10) == []
    assert repositorio.hashes_por_documento() == {}


@_sem_banco
def test_substituicao_que_falha_no_postgres_mantem_os_trechos_antigos(
    postgres: PostgresTrechosRepositorio,
) -> None:
    postgres.substituir_documento("a.md", "h-a", [trecho("a.md#antigo", vetor(1))])

    with pytest.raises(IntegrityError):
        postgres.substituir_documento(
            "a.md", "h-a2", [trecho("a.md#repetido", vetor(1)), trecho("a.md#repetido", vetor(1))]
        )

    assert [t.id for t in postgres.buscar_similares(vetor(1), k=10)] == ["a.md#antigo"]
    assert postgres.hashes_por_documento() == {"a.md": "h-a"}
