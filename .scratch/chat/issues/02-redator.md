# 02: Redator atrás de um port (Groq e sem LLM)

**Status:** ready-for-agent
**Blocked by:** nenhum
**Spec:** `.scratch/chat/spec.md` (seções "Contexto do redator" e "Redator")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O LLM entra só como redator: recebe a pergunta e um contexto já montado pelo código e devolve texto. Com `GROQ_API_KEY`, o `GroqRedator` chama a API compatível com a da OpenAI; sem chave, o `RedatorSemLLM` devolve os dados sem redação. O contexto é renderizado por uma função pura que marca os trechos do corpus como dado não confiável e já traz todo número calculado.

## Acceptance criteria

- [ ] `src/ai/redator.py`: `Redator` (Protocol com `nome` e `redigir(pergunta, contexto) -> str`), `RedatorIndisponivel`, `INSTRUCOES_REDATOR` com as 7 regras da spec e `RedatorSemLLM`.
- [ ] `src/ai/groq.py`: `GroqRedator` com `httpx2`, formato OpenAI de chat completions, `temperature` 0,2, `max_tokens` 2048, timeout de 30 s, sem tools. Erro HTTP, timeout e conteúdo vazio viram `RedatorIndisponivel`.
- [ ] `src/ai/contexto.py`: `Montagem` (fichas, sugestões, parâmetros e versão da política, trechos classificados, conflitos, observações) e `renderizar_contexto(montagem) -> str` com as seções e formatos da spec (centavos em `R$ 1.234,56`, meses com vírgula, aviso antes dos trechos, trechos delimitados com id, documento, data e classificação).
- [ ] `GROQ_API_KEY`, `GROQ_MODEL` (padrão `openai/gpt-oss-120b`) e `GROQ_BASE_URL` (padrão `https://api.groq.com/openai/v1`) em `Settings` e `.env.example`; `get_redator()` em `src/ai/dependencies.py`.
- [ ] Marcador `externo_llm` no `pyproject.toml` e no `conftest.py` (pula sem `GROQ_API_KEY`).
- [ ] Testes da spec para `contexto`, `GroqRedator` (`httpx2.MockTransport`) e `RedatorSemLLM`, e um `externo_llm` contra a Groq real.
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
