# 04: Registro de decisão

**Status:** ready-for-agent
**Blocked by:** 03
**Spec:** `.scratch/chat/spec.md` (seção "Registro de decisão")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Cada pergunta respondida pelo chat fica registrada com as respostas cruas do Jev (probabilidades e confiança), a faixa, a ação, os SKUs, os trechos que foram ao redator, o redator usado, a resposta e a duração. O registro serve para auditoria e para o M8 recalibrar as faixas. `GET /chat/registros` mostra os mais recentes.

## Acceptance criteria

- [ ] Migration `0004_registros_decisao` com a tabela e o índice da spec (`alembic upgrade head` e `downgrade` funcionam).
- [ ] `src/ai/registro.py`: `RegistroDecisao`, Protocol `RegistrosDecisao` (`gravar`, `listar(limite)`) e `InMemoryRegistrosDecisao`; `PostgresRegistrosDecisao` em `src/ai/postgres.py`.
- [ ] O mesmo teste de contrato roda contra os dois adapters (gravar, listar do mais recente, `limite`, jsonb com as probabilidades de volta).
- [ ] O `Copilot` grava um registro por pergunta respondida (inclusive esclarecimento e fora de escopo), com `duracao_ms`, e devolve o `registro_id`. Sem registro quando o Jev está fora do ar.
- [ ] `GET /chat/registros?limite=20` (1 a 100) com DTO HTTP.
- [ ] Testes HTTP e do `Copilot` cobrindo o registro.
- [ ] `uv run pytest -q -m "not externo"` verde, com o contrato Postgres rodando contra o banco local.

## Comments
