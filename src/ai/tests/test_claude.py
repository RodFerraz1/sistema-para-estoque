"""Testes do `ClaudeRedator` com o cliente do SDK sobre `httpx2.MockTransport`.

O teste com o marcador `externo_llm("anthropic")` chama a API real e é pulado sem `ANTHROPIC_API_KEY`.
"""
from __future__ import annotations

import json
from collections.abc import Callable

import anthropic
import httpx2
import pytest

from src.ai.claude import ClaudeRedator, criar_cliente_claude
from src.ai.redator import INSTRUCOES_REDATOR, RedatorIndisponivel, mensagem_do_usuario
from src.db.config import get_settings

MODELO = "claude-sonnet-5-5"
CONTEXTO = "## Fichas de SKU (dados do ERP)\n\n### TBC-BEGE-70140-01\n- Estoque disponível: 120 unidades"
PERGUNTA = "Como tá a toalha bege?"


def resposta_da_api(
    conteudo: list[dict],
    *,
    stop_reason: str = "end_turn",
    stop_details: dict | None = None,
) -> dict:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": MODELO,
        "content": conteudo,
        "stop_reason": stop_reason,
        "stop_details": stop_details,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def texto(conteudo: str) -> dict:
    return {"type": "text", "text": conteudo}


def redator_com(handler: Callable[[httpx2.Request], httpx2.Response]) -> ClaudeRedator:
    cliente = anthropic.Anthropic(
        api_key="chave-teste",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeRedator(cliente, MODELO)


def responde(corpo: dict, status: int = 200) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _: httpx2.Response(status, json=corpo)


def test_chama_o_messages_com_esforco_baixo_e_fallback_do_servidor() -> None:
    pedidos: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        pedidos.append(request)
        return httpx2.Response(200, json=resposta_da_api([texto("Tem 120 unidades.")]))

    redator_com(handler).redigir(PERGUNTA, CONTEXTO)

    [pedido] = pedidos
    corpo = json.loads(pedido.content)
    assert pedido.method == "POST"
    assert pedido.url.path == "/v1/messages"
    assert pedido.headers["x-api-key"] == "chave-teste"
    assert "server-side-fallback-2026-07-01" in pedido.headers["anthropic-beta"]
    assert corpo == {
        "model": MODELO,
        "max_tokens": 16000,
        "system": INSTRUCOES_REDATOR,
        "messages": [{"role": "user", "content": mensagem_do_usuario(PERGUNTA, CONTEXTO)}],
        "output_config": {"effort": "low"},
        "fallbacks": "default",
    }


def test_resposta_vira_so_o_texto_ignorando_raciocinio_e_fallback() -> None:
    conteudo = [
        {"type": "thinking", "thinking": "", "signature": "assinatura"},
        {
            "type": "fallback",
            "from": {"model": MODELO},
            "to": {"model": "claude-opus-4-8"},
            "trigger": {"type": "refusal", "category": "cyber"},
        },
        texto("  Tem 120 unidades"),
        texto(" em estoque.\n"),
    ]
    redator = redator_com(responde(resposta_da_api(conteudo)))

    assert redator.redigir(PERGUNTA, CONTEXTO) == "Tem 120 unidades em estoque."
    assert redator.nome == f"anthropic:{MODELO}"
    assert redator.usa_llm


def test_recusa_vira_redator_indisponivel_com_a_categoria() -> None:
    corpo = resposta_da_api([], stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber"})

    with pytest.raises(RedatorIndisponivel, match="cyber"):
        redator_com(responde(corpo)).redigir(PERGUNTA, CONTEXTO)


def test_recusa_sem_detalhes_vira_redator_indisponivel() -> None:
    corpo = resposta_da_api([texto("Parcial")], stop_reason="refusal")

    with pytest.raises(RedatorIndisponivel, match="recusou"):
        redator_com(responde(corpo)).redigir(PERGUNTA, CONTEXTO)


def test_texto_truncado_pelo_limite_de_tokens_vira_redator_indisponivel() -> None:
    corpo = resposta_da_api([texto("Tem 120")], stop_reason="max_tokens")

    with pytest.raises(RedatorIndisponivel, match="limite de tokens"):
        redator_com(responde(corpo)).redigir(PERGUNTA, CONTEXTO)


@pytest.mark.parametrize(
    "conteudo",
    [[], [{"type": "thinking", "thinking": "", "signature": "assinatura"}], [texto("   \n")]],
)
def test_texto_vazio_vira_redator_indisponivel(conteudo: list[dict]) -> None:
    with pytest.raises(RedatorIndisponivel, match="sem texto"):
        redator_com(responde(resposta_da_api(conteudo))).redigir(PERGUNTA, CONTEXTO)


@pytest.mark.parametrize(
    ("status", "mensagem"),
    [
        (401, "chave"),
        (403, "chave"),
        (429, "limite de requisições"),
        (500, "erro 500"),
        (529, "erro 529"),
    ],
)
def test_erro_http_vira_redator_indisponivel(status: int, mensagem: str) -> None:
    corpo = {"type": "error", "error": {"type": "api_error", "message": "falhou"}}

    with pytest.raises(RedatorIndisponivel, match=mensagem):
        redator_com(responde(corpo, status)).redigir(PERGUNTA, CONTEXTO)


@pytest.mark.parametrize("falha", [httpx2.ConnectError, httpx2.ReadTimeout])
def test_falha_de_conexao_ou_timeout_vira_redator_indisponivel(falha: type[httpx2.TransportError]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise falha("sem rede", request=request)

    with pytest.raises(RedatorIndisponivel, match="conexão"):
        redator_com(handler).redigir(PERGUNTA, CONTEXTO)


def test_cliente_tem_timeout_de_60_segundos_e_duas_novas_tentativas() -> None:
    cliente = criar_cliente_claude("chave-teste")

    assert cliente.api_key == "chave-teste"
    assert cliente.timeout == 60.0
    assert cliente.max_retries == 2


@pytest.mark.externo_llm("anthropic")
def test_claude_real_redige_com_o_numero_do_contexto() -> None:
    settings = get_settings()
    assert settings.anthropic_api_key, "o marcador externo_llm pula sem ANTHROPIC_API_KEY"
    redator = ClaudeRedator(criar_cliente_claude(settings.anthropic_api_key), settings.anthropic_model)

    resposta = redator.redigir("Quanto tem em estoque da TBC-BEGE-70140-01?", CONTEXTO)

    assert "120" in resposta
