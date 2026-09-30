"""Configuração do pytest para as suítes de `tests/` e de `src/`."""
from __future__ import annotations

import pytest

from src.db.config import get_settings


def pytest_runtest_setup(item: pytest.Item) -> None:
    settings = get_settings()
    if item.get_closest_marker("externo") and not settings.jev_key:
        pytest.skip("JEV_KEY vazio: não chama o Jev real")
    if item.get_closest_marker("externo_llm") and not settings.groq_api_key:
        pytest.skip("GROQ_API_KEY vazio: não chama o LLM real")
