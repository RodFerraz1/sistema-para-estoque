"""Adapter do `Redator` com a Groq, pela API de chat completions compatível com a da OpenAI."""
from __future__ import annotations

import httpx2

from src.ai.redator import INSTRUCOES_REDATOR, Redator, RedatorIndisponivel, mensagem_do_usuario

TEMPERATURA = 0.2
MAX_TOKENS = 2048
TIMEOUT_SEGUNDOS = 30.0


class GroqRedator(Redator):
    usa_llm = True

    def __init__(
        self,
        chave: str,
        modelo: str,
        base_url: str,
        *,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._modelo = modelo
        self._cliente = httpx2.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {chave}"},
            timeout=TIMEOUT_SEGUNDOS,
            transport=transport,
        )

    @property
    def nome(self) -> str:
        return f"groq:{self._modelo}"

    def redigir(self, pergunta: str, contexto: str) -> str:
        try:
            resposta = self._cliente.post("/chat/completions", json=self._corpo(pergunta, contexto))
            resposta.raise_for_status()
            conteudo = resposta.json()["choices"][0]["message"]["content"]
        except httpx2.HTTPError as erro:
            raise RedatorIndisponivel(f"Groq indisponível: {erro}") from erro
        except (ValueError, LookupError, TypeError) as erro:
            raise RedatorIndisponivel(f"Resposta da Groq fora do formato: {erro}") from erro
        if not isinstance(conteudo, str) or not conteudo.strip():
            raise RedatorIndisponivel("Resposta da Groq sem conteúdo")
        return conteudo.strip()

    def _corpo(self, pergunta: str, contexto: str) -> dict:
        return {
            "model": self._modelo,
            "messages": [
                {"role": "system", "content": INSTRUCOES_REDATOR},
                {"role": "user", "content": mensagem_do_usuario(pergunta, contexto)},
            ],
            "temperature": TEMPERATURA,
            "max_tokens": MAX_TOKENS,
        }
