# 01: Redator Claude e seleção do provedor

**Status:** ready-for-agent
**Blocked by:** nenhum
**Spec:** `.scratch/refinamentos/spec.md` (seção "Redator Claude")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Um segundo adapter do port `Redator`, o `ClaudeRedator`, com o SDK oficial `anthropic` e o Claude Opus 5.5 em esforço baixo, tratando recusa e com fallback do lado do servidor. A variável `REDATOR` escolhe o provedor, e em `auto` vale o primeiro com chave na ordem Anthropic, Groq, sem LLM. O marcador `externo_llm` passa a dizer de qual provedor o teste precisa.

Antes de escrever o adapter, invoque a skill `claude-api` e siga o que ela diz para o Python (parâmetros, betas, recusa, erros, versão do SDK). Se ela divergir desta spec num detalhe da API, vale a skill, e o desvio fica registrado no comentário.

Arquivos: `src/ai/claude.py` (novo), `src/ai/redator.py` (só `mensagem_do_usuario`), `src/ai/groq.py` (passa a usar `mensagem_do_usuario`), `src/ai/dependencies.py`, `src/db/config.py`, `conftest.py`, `pyproject.toml`, `uv.lock`, `.env.example`, `docker-compose.yml`, `src/ai/tests/test_claude.py` (novo), `src/ai/tests/test_groq.py`, `tests/smoke/test_chat.py` e um teste da seleção (por exemplo `src/ai/tests/test_dependencies.py`).

## Acceptance criteria

- [ ] `anthropic` (1.x) em `pyproject.toml` e `uv.lock`, convivendo com o `httpx2` do projeto.
- [ ] `mensagem_do_usuario(pergunta, contexto)` em `src/ai/redator.py`, usada pela Groq e pelo Claude (o texto enviado à Groq não muda).
- [ ] `src/ai/claude.py`: `ClaudeRedator(Redator)` (`usa_llm = True`, `nome` = `"anthropic:<modelo>"`) e `criar_cliente_claude(chave)` (timeout de 60 s, `max_retries=2`), com a chamada da spec: `beta.messages.create`, `max_tokens=16000`, `system=INSTRUCOES_REDATOR`, `output_config={"effort": "low"}`, `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`, sem `thinking`, sem parâmetros de amostragem e sem tools.
- [ ] Resposta: texto = junção dos blocos `text` (ignorando `thinking` e `fallback`), sem espaços nas pontas; `refusal` (com a categoria), `max_tokens` e texto vazio viram `RedatorIndisponivel`.
- [ ] Erros do SDK numa cadeia do mais específico para o mais geral (`AuthenticationError`/`PermissionDeniedError`, `RateLimitError`, `APIStatusError`, `APIConnectionError`), todos virando `RedatorIndisponivel` com mensagem própria.
- [ ] `Settings`: `REDATOR` (`auto` padrão, `anthropic`, `groq`, `sem_llm`), `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL` (padrão `claude-opus-5-5`), com validador que recusa `anthropic` ou `groq` sem a chave correspondente. `.env.example` atualizado.
- [ ] `get_redator()` aplica a regra da spec, com o cliente de cada provedor em `lru_cache`. A queda do redator escolhido continua indo para o `RedatorSemLLM`.
- [ ] `docker-compose.yml` repassa `ANTHROPIC_API_KEY` e `REDATOR` ao app.
- [ ] `externo_llm` com o provedor: `@pytest.mark.externo_llm("anthropic")` pula sem `ANTHROPIC_API_KEY`, `@pytest.mark.externo_llm("groq")` sem `GROQ_API_KEY`; descrição do marcador no `pyproject.toml` atualizada; os testes atuais da Groq declaram `"groq"`.
- [ ] O smoke do chat com a Groq real força o `GroqRedator` (com as duas chaves no `.env`, o `auto` escolheria o Claude).
- [ ] Testes da spec: `ClaudeRedator` com `httpx2.MockTransport` (corpo, cabeçalho do beta, ausência de `thinking` e `temperature`, blocos ignorados, `refusal`, `max_tokens`, texto vazio, 401, 429, 500, conexão), seleção do redator (os seis casos da spec) e um `externo_llm("anthropic")` que redige com o número do contexto.
- [ ] `uv run pytest -q -m "not externo and not externo_llm"` verde; `-m externo_llm` com os da Groq passando e o do Claude pulado (ou passando, se houver chave).

## Fora do escopo

- Instruções do redator, limpeza da redação e `reasoning_effort` da Groq (ticket 02).
- Cadeia de provedores na queda, streaming, cache de prompt, modelo que atendeu depois de um fallback no registro de decisão.
- README (ticket 06).

## Comments
