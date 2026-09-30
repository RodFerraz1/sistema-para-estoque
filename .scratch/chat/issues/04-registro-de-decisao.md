# 04: Registro de decisão

**Status:** done
**Blocked by:** 03
**Spec:** `.scratch/chat/spec.md` (seção "Registro de decisão")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Cada pergunta respondida pelo chat fica registrada com as respostas cruas do Jev (probabilidades e confiança), a faixa, a ação, os SKUs, os trechos que foram ao redator, o redator usado, a resposta e a duração. O registro serve para auditoria e para o M8 recalibrar as faixas. `GET /chat/registros` mostra os mais recentes.

## Acceptance criteria

- [x] Migration `0004_registros_decisao` com a tabela e o índice da spec (`alembic upgrade head` e `downgrade` funcionam).
- [x] `src/ai/registro.py`: `RegistroDecisao`, Protocol `RegistrosDecisao` (`gravar`, `listar(limite)`) e `InMemoryRegistrosDecisao`; `PostgresRegistrosDecisao` em `src/ai/postgres.py`.
- [x] O mesmo teste de contrato roda contra os dois adapters (gravar, listar do mais recente, `limite`, jsonb com as probabilidades de volta).
- [x] O `Copilot` grava um registro por pergunta respondida (inclusive esclarecimento e fora de escopo), com `duracao_ms`, e devolve o `registro_id`. Sem registro quando o Jev está fora do ar.
- [x] `GET /chat/registros?limite=20` (1 a 100) com DTO HTTP.
- [x] Testes HTTP e do `Copilot` cobrindo o registro.
- [x] `uv run pytest -q -m "not externo"` verde, com o contrato Postgres rodando contra o banco local.

## Comments

**2026-09-30 (agente):** pronto. Decisões e desvios:

- **`Faixa` e `Acao` saíram de `chat.py` para `src/ai/schemas.py`** (ao lado de `Intencao`): o `RegistroDecisao` usa os dois e o `chat.py` importa o `registro.py`, então deixá-los em `chat.py` criaria import circular. `src/api/schemas.py` passou a importar de `src.ai.schemas`.
- **`RegistroDecisao`** (Pydantic, frozen) em `src/ai/registro.py`, com os campos da tabela na mesma ordem e com os mesmos nomes. `entendimento` é o `Entendimento` inteiro; `intencao` e `confianca` repetem a intenção dele para o M8 filtrar sem abrir o jsonb. `InMemoryRegistrosDecisao` fica no próprio `registro.py`, como a spec pede (os outros adapters em memória do `ai` estão em `in_memory.py`).
- **`registro_id` virou obrigatório** em `RespostaCopilot` e em `RespostaChatResponse` (a spec diz `registro_id: UUID`). Em vez de `model_copy` depois de gravar, `responder` sorteia o `uuid4`, passa para `_decidir` (o corpo antigo de `responder`), mede a duração com `time.perf_counter`, grava e devolve a resposta. Assim não existe resposta sem registro.
- **`duracao_ms`** mede entendimento, montagem e redação, sem a gravação do registro. **`criado_em`** é `datetime.now(UTC)` no fim da decisão, gravado pela aplicação (a coluna também tem `DEFAULT now()`).
- **`skus`** é a lista depois do corte em `MAX_SKUS_POR_RESPOSTA` (os SKUs que viraram ficha ou sugestão) e fica vazia sem identificação. **`trechos`** são os ids que foram ao redator.
- **Migration sem CHECK** em `intencao`, `faixa` e `acao` (a `0002` tem CHECK nos enums): intenções e ações novas (M6, M7) não vão precisar de migration, e o `RegistroDecisao` já valida os valores na leitura.
- **Ordem de `listar`**: `ORDER BY criado_em DESC`. No `InMemoryRegistrosDecisao`, empate no `criado_em` sai do último gravado para o primeiro.
- **Falha ao gravar derruba a resposta** (a exceção propaga), com teste. Como `POST /chat` agora depende de `get_registros_decisao`, os testes HTTP trocam os registros pelo in-memory, como já trocavam o redator.
- **Endpoint** `GET /chat/registros?limite=20` (1 a 100, 422 fora disso), com `RegistroDecisaoResponse` e o `entendimento` no mesmo `EntendimentoResponse` do `POST /chat`. Ele não depende do Jev: funciona sem `JEV_KEY`.
- **Contrato** em `src/ai/tests/test_registro.py`, contra in-memory e Postgres (fixture com tabela temporária de backup, como a do `TrechosRepositorio`, para não apagar registros do banco de desenvolvimento).
- **Conferido no banco local**: `alembic upgrade head`, `downgrade -1` e `upgrade head` de novo. O smoke `tests/smoke/test_chat.py` (Jev e Groq reais) passou e o registro apareceu em `GET /chat/registros` com as probabilidades do Jev, redator `groq:openai/gpt-oss-120b` e 2,3 s.
- **Testes**: `uv run pytest -q -m "not externo"` com 440 passando (eram 414).
