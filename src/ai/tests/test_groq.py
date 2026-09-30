"""Testes do `GroqRedator` com `httpx2.MockTransport` no lugar da API.

O teste com o marcador `externo_llm` chama a Groq real e é pulado sem `GROQ_API_KEY`.
"""
from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from src.ai.groq import GroqRedator
from src.ai.redator import INSTRUCOES_REDATOR, RedatorIndisponivel
from src.db.config import get_settings

BASE_URL = "https://groq.test/openai/v1"
MODELO = "openai/gpt-oss-120b"
CONTEXTO = "## Fichas de SKU (dados do ERP)\n\n### TBC-BEGE-70140-01\n- Estoque disponível: 120 unidades"


def resposta_da_api(conteudo: str | None) -> dict:
    return {
        "id": "chatcmpl-1",
        "model": MODELO,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": conteudo}, "finish_reason": "stop"}],
    }


def redator_com(handler: Callable[[httpx2.Request], httpx2.Response]) -> GroqRedator:
    return GroqRedator("chave-teste", MODELO, BASE_URL, transport=httpx2.MockTransport(handler))


def test_chama_chat_completions_no_formato_da_openai_sem_tools() -> None:
    pedidos: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        pedidos.append(request)
        return httpx2.Response(200, json=resposta_da_api("Tem 120 unidades."))

    redator_com(handler).redigir("Como tá a toalha bege?", CONTEXTO)

    [pedido] = pedidos
    corpo = json.loads(pedido.content)
    assert pedido.method == "POST"
    assert str(pedido.url) == f"{BASE_URL}/chat/completions"
    assert pedido.headers["authorization"] == "Bearer chave-teste"
    assert corpo["model"] == MODELO
    assert corpo["temperature"] == 0.2
    assert corpo["max_tokens"] == 2048
    assert "tools" not in corpo
    [system, user] = corpo["messages"]
    assert system == {"role": "system", "content": INSTRUCOES_REDATOR}
    assert user["role"] == "user"
    assert CONTEXTO in user["content"]
    assert "Como tá a toalha bege?" in user["content"]


def test_timeout_do_pedido_e_de_30_segundos() -> None:
    timeouts: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        timeouts.append(request.extensions["timeout"])
        return httpx2.Response(200, json=resposta_da_api("Ok."))

    redator_com(handler).redigir("Pergunta", CONTEXTO)

    assert timeouts == [{"connect": 30.0, "read": 30.0, "write": 30.0, "pool": 30.0}]


def test_resposta_vira_o_texto_da_mensagem() -> None:
    redator = redator_com(lambda _: httpx2.Response(200, json=resposta_da_api("  Tem 120 unidades.\n")))

    assert redator.redigir("Pergunta", CONTEXTO) == "Tem 120 unidades."
    assert redator.nome == f"groq:{MODELO}"
    assert redator.usa_llm


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_erro_http_vira_redator_indisponivel(status: int) -> None:
    redator = redator_com(lambda _: httpx2.Response(status, json={"error": {"message": "falhou"}}))

    with pytest.raises(RedatorIndisponivel):
        redator.redigir("Pergunta", CONTEXTO)


def test_timeout_vira_redator_indisponivel() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("demorou", request=request)

    with pytest.raises(RedatorIndisponivel):
        redator_com(handler).redigir("Pergunta", CONTEXTO)


def test_falha_de_conexao_vira_redator_indisponivel() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("sem rede", request=request)

    with pytest.raises(RedatorIndisponivel):
        redator_com(handler).redigir("Pergunta", CONTEXTO)


@pytest.mark.parametrize("conteudo", [None, "", "   \n"])
def test_conteudo_vazio_vira_redator_indisponivel(conteudo: str | None) -> None:
    redator = redator_com(lambda _: httpx2.Response(200, json=resposta_da_api(conteudo)))

    with pytest.raises(RedatorIndisponivel):
        redator.redigir("Pergunta", CONTEXTO)


@pytest.mark.parametrize("corpo", [b"<html>502</html>", b'{"choices": []}', b'{"inesperado": true}'])
def test_resposta_fora_do_formato_vira_redator_indisponivel(corpo: bytes) -> None:
    redator = redator_com(lambda _: httpx2.Response(200, content=corpo))

    with pytest.raises(RedatorIndisponivel):
        redator.redigir("Pergunta", CONTEXTO)


@pytest.mark.externo_llm
def test_groq_real_redige_com_o_numero_do_contexto() -> None:
    settings = get_settings()
    assert settings.groq_api_key, "o marcador externo_llm pula sem GROQ_API_KEY"
    redator = GroqRedator(settings.groq_api_key, settings.groq_model, settings.groq_base_url)

    resposta = redator.redigir("Quanto tem em estoque da TBC-BEGE-70140-01?", CONTEXTO)

    assert "120" in resposta
