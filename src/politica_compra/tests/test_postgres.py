"""Testes de integração do `PostgresPoliticaCompraRepositorio`.

Requerem `docker compose up` + `alembic upgrade head`. As versões criadas
por cada teste são apagadas no teardown para não mudar a política ativa do
banco de desenvolvimento.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text

from src.db.engine import get_engine
from src.politica_compra.postgres import PostgresPoliticaCompraRepositorio
from src.politica_compra.schemas import (
    CriterioFornecedor,
    LeadTimeBase,
    MotivoDestaque,
    PARAMETROS_V1,
    SazonalidadeModo,
)


def _db_available() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.politicas_compra LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_available(),
    reason="Postgres com copilot.politicas_compra precisa estar disponível",
)


def _maior_versao() -> int:
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT MAX(versao) FROM copilot.politicas_compra")).scalar_one()


@pytest.fixture
def repo() -> Iterator[PostgresPoliticaCompraRepositorio]:
    antes = _maior_versao()
    yield PostgresPoliticaCompraRepositorio(get_engine())
    with get_engine().begin() as conn:
        conn.execute(
            text("DELETE FROM copilot.politicas_compra WHERE versao > :v"), {"v": antes}
        )


def test_migration_grava_a_v1_com_os_valores_da_spec() -> None:
    v1 = PostgresPoliticaCompraRepositorio(get_engine()).versao(1)

    assert v1 is not None
    assert v1.parametros == PARAMETROS_V1


def test_salvar_nova_versao_round_trip_e_vira_ativa(
    repo: PostgresPoliticaCompraRepositorio,
) -> None:
    anterior = repo.ativa()
    novos = PARAMETROS_V1.model_copy(
        update={
            "teto_meses": 2.5,
            "ciclo_compra_meses": 1.5,
            "lead_time_base": LeadTimeBase.MAIOR,
            "criterio_fornecedor": CriterioFornecedor.MENOR_LEAD_TIME,
            "sazonalidade_modo": SazonalidadeModo.IGNORAR,
            "meses_quentes": (12, 1),
            "motivos_de_destaque": (MotivoDestaque.ENCALHE, MotivoDestaque.VIOLA_TETO),
        }
    )

    salva = repo.salvar_nova_versao(novos)

    assert salva.versao > anterior.versao
    assert salva.parametros == novos
    assert salva.criada_em.tzinfo is not None
    assert repo.ativa() == salva


def test_versoes_antigas_continuam_gravadas(
    repo: PostgresPoliticaCompraRepositorio,
) -> None:
    anterior = repo.ativa()

    repo.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"teto_meses": 4.0}))

    assert repo.versao(anterior.versao) == anterior


@pytest.mark.parametrize("motivos", [tuple(MotivoDestaque), ()], ids=["todos", "nenhum"])
def test_motivos_de_destaque_cabem_na_coluna(
    repo: PostgresPoliticaCompraRepositorio, motivos: tuple[MotivoDestaque, ...]
) -> None:
    salva = repo.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"motivos_de_destaque": motivos}))

    assert repo.versao(salva.versao) == salva
    assert salva.parametros.motivos_de_destaque == motivos
