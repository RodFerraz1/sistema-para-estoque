"""Fixtures do smoke test end-to-end.

Sobe o app FastAPI contra o Postgres real (do `docker compose up`),
aplica as migrations (`alembic upgrade head`), popula o seed
(`scripts.seed.run`) e ingere o `corpus/` com o embedding de verdade. Se
o Postgres não estiver acessível, o suite inteiro é `skip`.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.seed import run as run_seed
from src.ai.dependencies import get_embedder, get_trechos_repositorio
from src.ai.ingestao import ingerir
from src.db.config import get_settings
from src.db.engine import get_engine
from src.main import app
from src.usuarios.postgres import PostgresUsuariosRepositorio
from tests.fakes import make_usuario

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _postgres_up() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _banco_migrado_e_populado() -> None:
    if not _postgres_up():
        pytest.skip("Postgres precisa estar disponível (docker compose up)")
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    run_seed()
    ingerir(get_settings().corpus_dir, get_embedder(), get_trechos_repositorio())
    _gravar_usuario_fake()


def _gravar_usuario_fake() -> None:
    """Avisos, decisões e registros apontam para `copilot.usuarios`, então o usuário fake do
    `conftest.py` da raiz precisa existir no banco. Fica desativado: ninguém entra com ele."""
    repo = PostgresUsuariosRepositorio(get_engine())
    fake = make_usuario().model_copy(
        update={"nome": "Testes automáticos", "email": "testes-automaticos@copilot.teste", "ativo": False}
    )
    if repo.por_id(fake.id) is None:
        repo.gravar(fake)


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sku_code() -> str:
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT sku_code FROM erp.skus ORDER BY sku_code LIMIT 1")
        ).one()
    return row[0]


@pytest.fixture
def criados() -> Iterator[dict[str, list[UUID]]]:
    """Os ids do que o teste gravou, por tabela do `copilot`, para apagar no fim."""
    ids: dict[str, list[UUID]] = {
        "avisos": [],
        "avisos_gondola": [],
        "decisoes_compra": [],
        "cobrancas_entrega": [],
        "verificacoes_gondola": [],
    }
    yield ids
    with get_engine().begin() as conn:
        for tabela, lista in ids.items():
            conn.execute(text(f"DELETE FROM copilot.{tabela} WHERE id = ANY(:ids)"), {"ids": lista})


@contextmanager
def _tabela_restaurada(tabela: str) -> Iterator[None]:
    backup = f"backup_{tabela}_smoke"
    with get_engine().connect() as conn:
        conn.execute(text(f"CREATE TEMP TABLE {backup} AS SELECT * FROM copilot.{tabela}"))
        conn.commit()
        try:
            yield
        finally:
            conn.execute(text(f"DELETE FROM copilot.{tabela}"))
            conn.execute(text(f"INSERT INTO copilot.{tabela} SELECT * FROM {backup}"))
            conn.execute(text(f"DROP TABLE {backup}"))
            conn.commit()


@pytest.fixture
def episodios_restaurados() -> Iterator[None]:
    """A varredura do `/notificacoes` abre e fecha episódios do seed inteiro, e avisos,
    decisões e verificações gravam eventos: devolve no fim os episódios de antes."""
    with _tabela_restaurada("episodios_alerta"):
        yield


@pytest.fixture
def setores_restaurados() -> Iterator[None]:
    """O aviso de gôndola vazia e a verificação regravam o setor conhecido do SKU."""
    with _tabela_restaurada("setores_sku"):
        yield


@pytest.fixture
def capacidades_restauradas() -> Iterator[None]:
    with _tabela_restaurada("capacidades_gondola"):
        yield
