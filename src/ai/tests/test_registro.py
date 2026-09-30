"""Contrato do `RegistrosDecisao`.

Roda contra `InMemoryRegistrosDecisao` e `PostgresRegistrosDecisao`. O Postgres
requer `docker compose up` + `alembic upgrade head` e é pulado sem banco. Como
`listar` olha a tabela inteira, a fixture guarda os registros já gravados numa
tabela temporária, esvazia a tabela e devolve os registros no teardown.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.ai.postgres import PostgresRegistrosDecisao
from src.ai.registro import InMemoryRegistrosDecisao, RegistroDecisao, RegistrosDecisao
from src.db.engine import get_engine
from tests.fakes import make_entendimento

INICIO = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.registros_decisao LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(),
    reason="Postgres com copilot.registros_decisao precisa estar disponível",
)


@pytest.fixture
def postgres() -> Iterator[PostgresRegistrosDecisao]:
    with get_engine().connect() as conn:
        conn.execute(
            text("CREATE TEMP TABLE backup_registros AS SELECT * FROM copilot.registros_decisao")
        )
        conn.execute(text("DELETE FROM copilot.registros_decisao"))
        conn.commit()
        try:
            yield PostgresRegistrosDecisao(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.registros_decisao"))
            conn.execute(
                text("INSERT INTO copilot.registros_decisao SELECT * FROM backup_registros")
            )
            conn.execute(text("DROP TABLE backup_registros"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def registros(request: pytest.FixtureRequest) -> RegistrosDecisao:
    if request.param == "memoria":
        return InMemoryRegistrosDecisao()
    return request.getfixturevalue("postgres")


def registro(minutos: int = 0, **campos: object) -> RegistroDecisao:
    return RegistroDecisao.model_validate(
        {
            "id": uuid4(),
            "criado_em": INICIO + timedelta(minutes=minutos),
            "pergunta": "Como tá a toalha banho conforto bege?",
            "intencao": "situacao_sku",
            "confianca": 0.93,
            "faixa": "alta",
            "acao": "respondeu",
            "skus": ["TBC-BEGE-70140-01", "TBC-BEGE-70140-03"],
            "entendimento": make_entendimento(
                "situacao_sku",
                0.93,
                produto="Toalha Banho Conforto",
                confianca_produto=0.71,
                probabilidades_intencao={"situacao_sku": 0.93, "sugestao_compra": 0.07},
                probabilidades_produto={"Toalha Banho Conforto": 0.71, "nenhum": 0.29},
                modelo="jev-1.13.0",
            ),
            "trechos": ["contratos/katrina.md#prazos", "reunioes/q1.md#katrina"],
            "redator": "groq:openai/gpt-oss-120b",
            "resposta": "A toalha bege tem 40 unidades.",
            "duracao_ms": 3412,
            **campos,
        }
    )


def test_gravar_e_listar_devolve_o_registro_inteiro(registros: RegistrosDecisao) -> None:
    gravado = registro()

    registros.gravar(gravado)

    assert registros.listar(10) == [gravado]


def test_entendimento_volta_com_as_probabilidades(registros: RegistrosDecisao) -> None:
    registros.gravar(registro())

    [lido] = registros.listar(1)

    assert lido.entendimento.intencao.probabilidades == {"situacao_sku": 0.93, "sugestao_compra": 0.07}
    assert lido.entendimento.produto.probabilidades == {"Toalha Banho Conforto": 0.71, "nenhum": 0.29}
    assert lido.entendimento.modelo == "jev-1.13.0"


def test_resposta_em_codigo_grava_sem_redator_skus_nem_trechos(registros: RegistrosDecisao) -> None:
    gravado = registro(
        faixa="baixa", acao="pediu_esclarecimento", skus=[], trechos=[], redator=None, confianca=0.31
    )

    registros.gravar(gravado)

    assert registros.listar(1) == [gravado]


def test_listar_devolve_do_mais_recente_para_o_mais_antigo(registros: RegistrosDecisao) -> None:
    meio, antigo, recente = registro(5), registro(0), registro(10)
    for r in (meio, antigo, recente):
        registros.gravar(r)

    assert [r.id for r in registros.listar(10)] == [recente.id, meio.id, antigo.id]


def test_listar_respeita_o_limite(registros: RegistrosDecisao) -> None:
    gravados = [registro(minutos) for minutos in range(5)]
    for r in gravados:
        registros.gravar(r)

    assert [r.id for r in registros.listar(2)] == [gravados[4].id, gravados[3].id]


def test_listar_sem_registros_devolve_lista_vazia(registros: RegistrosDecisao) -> None:
    assert registros.listar(10) == []
