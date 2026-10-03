"""Configuração do pytest para as suítes de `tests/` e de `src/`."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from src.db.config import get_settings
from src.usuarios.schemas import PAPEIS, Usuario
from tests.fakes import make_usuario

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


@pytest.fixture(autouse=True)
def usuario_logado(request: pytest.FixtureRequest) -> Iterator[Usuario | None]:
    """Nos testes HTTP, toda requisição entra como este usuário fake, com todos os papéis, e
    sem exigir o cabeçalho `X-Requested-With`. Para outros papéis, marque o teste (ou o
    módulo) com `@pytest.mark.papeis("vendas", ...)`. Para o login de verdade, sem fake,
    marque com `@pytest.mark.login_de_verdade`."""
    if request.node.get_closest_marker("login_de_verdade"):
        yield None
        return
    from src.main import app
    from src.usuarios.dependencies import exige_x_requested_with, usuario_atual

    marcador = request.node.get_closest_marker("papeis")
    usuario = make_usuario(papeis=list(marcador.args) if marcador else list(PAPEIS))
    app.dependency_overrides[usuario_atual] = lambda: usuario
    app.dependency_overrides[exige_x_requested_with] = lambda: None
    yield usuario
    app.dependency_overrides.pop(usuario_atual, None)
    app.dependency_overrides.pop(exige_x_requested_with, None)
