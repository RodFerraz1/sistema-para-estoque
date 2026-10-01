"""Adapter do `Redator` com o Claude, pelo SDK oficial da Anthropic."""
from __future__ import annotations

import anthropic

from src.ai.redator import INSTRUCOES_REDATOR, Redator, RedatorIndisponivel, mensagem_do_usuario

MAX_TOKENS = 16000
ESFORCO = "low"
BETA_FALLBACK = "server-side-fallback-2026-07-01"
TIMEOUT_SEGUNDOS = 60.0
NOVAS_TENTATIVAS = 2


def criar_cliente_claude(chave: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=chave, timeout=TIMEOUT_SEGUNDOS, max_retries=NOVAS_TENTATIVAS)


class ClaudeRedator(Redator):
    """No Sonnet 5.5 o raciocínio fica ligado, e o esforço baixo é o que o encurta. Numa
    recusa dos classificadores, o `fallbacks="default"` repete o pedido no servidor, no modelo
    recomendado para a categoria; `refusal` na resposta quer dizer que a cadeia inteira recusou."""

    usa_llm = True

    def __init__(self, cliente: anthropic.Anthropic, modelo: str) -> None:
        self._cliente = cliente
        self._modelo = modelo

    @property
    def nome(self) -> str:
        return f"anthropic:{self._modelo}"

    def redigir(self, pergunta: str, contexto: str) -> str:
        try:
            resposta = self._cliente.beta.messages.create(
                model=self._modelo,
                max_tokens=MAX_TOKENS,
                system=INSTRUCOES_REDATOR,
                messages=[{"role": "user", "content": mensagem_do_usuario(pergunta, contexto)}],
                output_config={"effort": ESFORCO},
                betas=[BETA_FALLBACK],
                fallbacks="default",
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as erro:
            raise RedatorIndisponivel(f"Anthropic recusou a chave ({erro.status_code})") from erro
        except anthropic.RateLimitError as erro:
            raise RedatorIndisponivel("Anthropic: limite de requisições atingido") from erro
        except anthropic.APIStatusError as erro:
            raise RedatorIndisponivel(f"Anthropic respondeu com erro {erro.status_code}") from erro
        except anthropic.APIConnectionError as erro:
            raise RedatorIndisponivel(f"Sem conexão com a Anthropic: {erro}") from erro

        if resposta.stop_reason == "refusal":
            categoria = resposta.stop_details.category if resposta.stop_details else None
            raise RedatorIndisponivel(f"O Claude recusou a redação (categoria: {categoria or 'não informada'})")
        if resposta.stop_reason == "max_tokens":
            raise RedatorIndisponivel("A redação do Claude passou do limite de tokens")
        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()
        if not texto:
            raise RedatorIndisponivel("Resposta do Claude sem texto")
        return texto
