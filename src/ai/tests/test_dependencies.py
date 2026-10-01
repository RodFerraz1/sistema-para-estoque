"""Testes da seleção do redator por `REDATOR` e pela chave da Anthropic."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.ai.claude import ClaudeRedator
from src.ai.dependencies import get_redator
from src.ai.redator import RedatorSemLLM
from src.db.config import get_settings
from src.main import create_app


def configurar(monkeypatch: pytest.MonkeyPatch, redator: str, *, anthropic: str = "") -> None:
    monkeypatch.setenv("REDATOR", redator)
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-teste")


def test_auto_com_a_chave_escolhe_o_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto", anthropic="chave-anthropic")

    redator = get_redator()

    assert isinstance(redator, ClaudeRedator)
    assert redator.nome == "anthropic:claude-teste"


def test_auto_sem_chave_escolhe_o_sem_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto")

    assert isinstance(get_redator(), RedatorSemLLM)


def test_auto_e_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto")
    monkeypatch.delenv("REDATOR")

    assert get_settings().redator == "auto"


def test_anthropic_com_a_chave_escolhe_o_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "anthropic", anthropic="chave-anthropic")

    assert isinstance(get_redator(), ClaudeRedator)


def test_sem_llm_ignora_as_chaves(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "sem_llm", anthropic="chave-anthropic")

    assert isinstance(get_redator(), RedatorSemLLM)


def test_anthropic_sem_a_chave_recusa_a_configuracao(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "anthropic")

    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        get_settings()


def test_provedor_desconhecido_recusa_a_configuracao(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "openai")

    with pytest.raises(ValidationError):
        get_settings()


def test_a_aplicacao_nao_sobe_com_o_provedor_sem_a_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "anthropic")

    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        create_app()
