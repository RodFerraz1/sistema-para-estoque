"""Configuração do pytest para as suítes de `tests/` e de `src/`."""
from __future__ import annotations

import pytest

from src.db.config import get_settings


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("externo") and not get_settings().jev_key:
        pytest.skip("JEV_KEY vazio: não chama o Jev real")
