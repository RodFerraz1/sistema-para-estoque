"""Testes da seleção do redator por `REDATOR` e pelas chaves de cada provedor."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.ai.claude import ClaudeRedator
from src.ai.dependencies import get_redator
from src.ai.groq import GroqRedator
from src.ai.redator import RedatorSemLLM
from src.db.config import Settings, get_settings
from src.main import create_app


def configurar(
    monkeypatch: pytest.MonkeyPatch, redator: str, *, anthropic: str = "", groq: str = ""
) -> None:
    monkeypatch.setenv("REDATOR", redator)
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-teste")
    monkeypatch.setenv("GROQ_API_KEY", groq)
    monkeypatch.setenv("GROQ_MODEL", "llama-teste")


def test_auto_com_as_duas_chaves_escolhe_o_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto", anthropic="chave-anthropic", groq="chave-groq")

    redator = get_redator()

    assert isinstance(redator, ClaudeRedator)
    assert redator.nome == "anthropic:claude-teste"


def test_auto_so_com_a_chave_da_groq_escolhe_a_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto", groq="chave-groq")

    redator = get_redator()

    assert isinstance(redator, GroqRedator)
    assert redator.nome == "groq:llama-teste"


def test_auto_sem_chave_escolhe_o_sem_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto")

    assert isinstance(get_redator(), RedatorSemLLM)


def test_auto_e_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "auto")
    monkeypatch.delenv("REDATOR")

    assert get_settings().redator == "auto"


def test_groq_com_as_duas_chaves_escolhe_a_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "groq", anthropic="chave-anthropic", groq="chave-groq")

    assert isinstance(get_redator(), GroqRedator)


def test_anthropic_com_as_duas_chaves_escolhe_o_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "anthropic", anthropic="chave-anthropic", groq="chave-groq")

    assert isinstance(get_redator(), ClaudeRedator)


def test_sem_llm_ignora_as_chaves(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "sem_llm", anthropic="chave-anthropic", groq="chave-groq")

    assert isinstance(get_redator(), RedatorSemLLM)


@pytest.mark.parametrize(
    ("provedor", "variavel", "outra_chave"),
    [
        ("anthropic", "ANTHROPIC_API_KEY", {"groq": "chave-groq"}),
        ("groq", "GROQ_API_KEY", {"anthropic": "chave-anthropic"}),
    ],
)
def test_provedor_sem_a_chave_dele_recusa_a_configuracao(
    monkeypatch: pytest.MonkeyPatch, provedor: str, variavel: str, outra_chave: dict[str, str]
) -> None:
    configurar(monkeypatch, provedor, **outra_chave)

    with pytest.raises(ValidationError, match=variavel):
        get_settings()


def test_provedor_desconhecido_recusa_a_configuracao(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "openai")

    with pytest.raises(ValidationError):
        get_settings()


def test_a_aplicacao_nao_sobe_com_o_provedor_sem_a_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    configurar(monkeypatch, "anthropic")

    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        create_app()


def test_reasoning_effort_da_groq_e_baixo_por_padrao_e_pode_ficar_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_REASONING_EFFORT", raising=False)
    assert Settings(_env_file=None).groq_reasoning_effort == "low"

    monkeypatch.setenv("GROQ_REASONING_EFFORT", "")
    assert Settings(_env_file=None).groq_reasoning_effort == ""
