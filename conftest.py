"""Configuração do pytest para as suítes de `tests/` e de `src/`."""
from __future__ import annotations

import pytest

from src.db.config import get_settings

CHAVES_DOS_LLMS = {"anthropic": "ANTHROPIC_API_KEY"}


def pytest_runtest_setup(item: pytest.Item) -> None:
    settings = get_settings()
    if item.get_closest_marker("externo") and not settings.jev_key:
        pytest.skip("JEV_KEY vazio: não chama o Jev real")
    marcador = item.get_closest_marker("externo_llm")
    if marcador:
        provedor = marcador.args[0] if marcador.args else None
        if provedor not in CHAVES_DOS_LLMS:
            raise pytest.UsageError(f"externo_llm precisa de um provedor de {sorted(CHAVES_DOS_LLMS)}: {item.nodeid}")
        variavel = CHAVES_DOS_LLMS[provedor]
        if not getattr(settings, variavel.lower()):
            pytest.skip(f"{variavel} vazio: não chama o LLM real")
