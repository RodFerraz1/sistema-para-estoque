"""Fixtures do smoke test end-to-end.

Sobe o app FastAPI contra o Postgres real (do `docker compose up`),
com o schema `erp` migrado (`alembic upgrade head`) e o seed populado
(`scripts.seed.run`). Se o banco não estiver acessível ou não estiver
migrado, o suite inteiro é `skip` - o mesmo padrão do
`tests/test_seed_smoke.py`.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.seed import run as run_seed
from src.db.engine import get_engine
from src.main import app

pytestmark = pytest.mark.smoke


def _db_ready() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.skus LIMIT 1"))
        return True
    except Exception:
        return False


if not _db_ready():
    pytest.skip(
        "Postgres com schema erp precisa estar disponível "
        "(docker compose up + alembic upgrade head)",
        allow_module_level=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _seed_once() -> None:
    run_seed()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def sku_code(client: TestClient) -> str:
    """Um `sku_code` real qualquer do seed, escolhido pelo endpoint público."""
    with get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT sku_code FROM erp.skus ORDER BY sku_code LIMIT 1")
        ).one()
    return row[0]
