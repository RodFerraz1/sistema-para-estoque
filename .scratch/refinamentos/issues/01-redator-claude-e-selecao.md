# 01: Redator Claude e seleção do provedor

**Status:** done
**Blocked by:** nenhum
**Spec:** `.scratch/refinamentos/spec.md` (seção "Redator Claude")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Um segundo adapter do port `Redator`, o `ClaudeRedator`, com o SDK oficial `anthropic` e o Claude Opus 5.5 em esforço baixo, tratando recusa e com fallback do lado do servidor. A variável `REDATOR` escolhe o provedor, e em `auto` vale o primeiro com chave na ordem Anthropic, Groq, sem LLM. O marcador `externo_llm` passa a dizer de qual provedor o teste precisa.

Antes de escrever o adapter, invoque a skill `claude-api` e siga o que ela diz para o Python (parâmetros, betas, recusa, erros, versão do SDK). Se ela divergir desta spec num detalhe da API, vale a skill, e o desvio fica registrado no comentário.

Arquivos: `src/ai/claude.py` (novo), `src/ai/redator.py` (só `mensagem_do_usuario`), `src/ai/groq.py` (passa a usar `mensagem_do_usuario`), `src/ai/dependencies.py`, `src/db/config.py`, `conftest.py`, `pyproject.toml`, `uv.lock`, `.env.example`, `docker-compose.yml`, `src/ai/tests/test_claude.py` (novo), `src/ai/tests/test_groq.py`, `tests/smoke/test_chat.py` e um teste da seleção (por exemplo `src/ai/tests/test_dependencies.py`).

## Acceptance criteria

- [x] `anthropic` (1.x) em `pyproject.toml` e `uv.lock`, convivendo com o `httpx2` do projeto.
- [x] `mensagem_do_usuario(pergunta, contexto)` em `src/ai/redator.py`, usada pela Groq e pelo Claude (o texto enviado à Groq não muda).
- [x] `src/ai/claude.py`: `ClaudeRedator(Redator)` (`usa_llm = True`, `nome` = `"anthropic:<modelo>"`) e `criar_cliente_claude(chave)` (timeout de 60 s, `max_retries=2`), com a chamada da spec: `beta.messages.create`, `max_tokens=16000`, `system=INSTRUCOES_REDATOR`, `output_config={"effort": "low"}`, `betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`, sem `thinking`, sem parâmetros de amostragem e sem tools.
- [x] Resposta: texto = junção dos blocos `text` (ignorando `thinking` e `fallback`), sem espaços nas pontas; `refusal` (com a categoria), `max_tokens` e texto vazio viram `RedatorIndisponivel`.
- [x] Erros do SDK numa cadeia do mais específico para o mais geral (`AuthenticationError`/`PermissionDeniedError`, `RateLimitError`, `APIStatusError`, `APIConnectionError`), todos virando `RedatorIndisponivel` com mensagem própria.
- [x] `Settings`: `REDATOR` (`auto` padrão, `anthropic`, `groq`, `sem_llm`), `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL` (padrão `claude-opus-5-5`), com validador que recusa `anthropic` ou `groq` sem a chave correspondente. `.env.example` atualizado.
- [x] `get_redator()` aplica a regra da spec, com o cliente de cada provedor em `lru_cache`. A queda do redator escolhido continua indo para o `RedatorSemLLM`.
- [x] `docker-compose.yml` repassa `ANTHROPIC_API_KEY` e `REDATOR` ao app.
- [x] `externo_llm` com o provedor: `@pytest.mark.externo_llm("anthropic")` pula sem `ANTHROPIC_API_KEY`, `@pytest.mark.externo_llm("groq")` sem `GROQ_API_KEY`; descrição do marcador no `pyproject.toml` atualizada; os testes atuais da Groq declaram `"groq"`.
- [x] O smoke do chat com a Groq real força o `GroqRedator` (com as duas chaves no `.env`, o `auto` escolheria o Claude).
- [x] Testes da spec: `ClaudeRedator` com `httpx2.MockTransport` (corpo, cabeçalho do beta, ausência de `thinking` e `temperature`, blocos ignorados, `refusal`, `max_tokens`, texto vazio, 401, 429, 500, conexão), seleção do redator (os seis casos da spec) e um `externo_llm("anthropic")` que redige com o número do contexto.
- [x] `uv run pytest -q -m "not externo and not externo_llm"` verde; `-m externo_llm` com os da Groq passando e o do Claude pulado (ou passando, se houver chave).

## Fora do escopo

- Instruções do redator, limpeza da redação e `reasoning_effort` da Groq (ticket 02).
- Cadeia de provedores na queda, streaming, cache de prompt, modelo que atendeu depois de um fallback no registro de decisão.
- README (ticket 06).

## Comments

**2026-10-01 (agente):** pronto. Decisões e desvios:

- **Skill `claude-api` seguida, sem divergência com a spec**: `beta.messages.create` sem streaming, `max_tokens=16000`, `output_config={"effort": "low"}`, sem `thinking` (no Opus 5.5 o raciocínio não desliga), sem amostragem, sem tools, `betas=["server-side-fallback-2026-07-01"]` com `fallbacks="default"` (o par certo para a forma escalar; a forma em lista usa o `-2026-06-01`). O SDK instalado (`anthropic` 1.11.0, com `httpx2` 2.13.1) tipa `fallbacks`, então não precisou de `extra_body`. Pin `anthropic>=1,<2`, no estilo de faixa que a skill recomenda.
- **Recusa**: decide pelo `stop_reason`, nunca pelo `stop_details`, que pode vir nulo; sem detalhe, a mensagem diz "categoria: não informada". Blocos `fallback` e `thinking` são ignorados e os `text` são concatenados sem separador.
- **Erros**: cadeia `AuthenticationError`/`PermissionDeniedError` -> `RateLimitError` -> `APIStatusError` -> `APIConnectionError` (o `APITimeoutError` é subclasse dela). Erro de formato da resposta (`APIResponseValidationError`) não entra, porque o SDK não valida em modo estrito por padrão e a spec não pede.
- **Seleção**: a regra fica em `get_redator()` (com `_provedor_do_redator` resolvendo o `auto`); o validador do `Settings` recusa `anthropic`/`groq` sem a chave e um valor fora dos quatro (`Literal`). `_claude` em `lru_cache` como `_groq` e `_jev`.
- **Desvio: `src/main.py`**, fora da lista de arquivos. O `Settings` só era lido na primeira requisição, então "a aplicação não sobe" não valia: o `create_app()` agora chama `get_settings()` e a configuração inválida derruba a subida (testado).
- **Testes de seleção**: os dois de `get_redator` que estavam em `test_redator.py` foram para `src/ai/tests/test_dependencies.py`, que fixa `REDATOR` e as duas chaves por `monkeypatch` em todo caso (senão o resultado dependeria do `.env` local). Além dos seis da spec: `auto` é o padrão, `anthropic` com as duas chaves e provedor desconhecido.
- **`externo_llm` sem provedor** (ou com provedor desconhecido) é erro de uso do pytest, não pulo silencioso.
- **Smoke**: força a Groq com `monkeypatch.setenv("REDATOR", "groq")` em vez de `dependency_overrides`, para passar pela seleção real.
- **`.env.example`**: `REDATOR`, `ANTHROPIC_API_KEY` e `ANTHROPIC_MODEL` depois do `JEV_MODEL`. O commit leva só essas três linhas; a mudança do dev no arquivo (fim de linha do `FASTEMBED_CACHE_PATH`) ficou fora do índice. Como o ambiente não aceita `git add -p` (interativo), o índice foi montado a partir do `HEAD` com as três linhas.
- **Testes**: `-m "not externo and not externo_llm"` com 765 passando (eram 740). `-m externo_llm`: os dois da Groq passando (unitário e smoke) e o do Claude pulado, porque não há `ANTHROPIC_API_KEY` no `.env`. O `ClaudeRedator` não foi exercitado contra a API real: latência, custo e se o esforço baixo basta para seguir as instruções ficam para a rodada do ticket 02/06 com a chave.
- **Para o ticket 02**: `INSTRUCOES_REDATOR` vai inteira no `system` do Claude e da Groq, e `mensagem_do_usuario` é a única montagem da mensagem do usuário. O texto do Claude chega com `strip()`, mas sem limpeza: o `limpar_redacao` no `Copilot._redigir` vale para os dois. O `reasoning_effort` da Groq continua por fazer.
