# 01: Fundação técnica

**Status:** done
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/copilot-compras/spec.md`

## What to build

Um desenvolvedor consegue clonar o repositório, rodar `docker compose up` e ter a aplicação FastAPI + Postgres com pgvector no ar. O endpoint `/health` responde 200 confirmando que app e banco estão saudáveis. Projeto Python configurado com `uv`, estrutura de diretórios inicial preparada pros módulos que virão nos próximos tickets.

## Acceptance criteria

- [x] `pyproject.toml` configurado com `uv`, Python 3.12+, dependências mínimas (FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, psycopg).
- [x] `docker-compose.yml` sobe Postgres 16 com extensão `pgvector` habilitada e a app FastAPI em container separado.
- [x] `docker compose up` funciona a partir de repositório limpo, sem passos manuais adicionais.
- [x] `GET /health` retorna `{"status": "ok", "db": "ok"}` com status 200 quando app e banco estão saudáveis.
- [x] `GET /health` retorna status apropriado (não 200) quando o banco está inacessível.
- [x] Estrutura de diretórios inicial: `src/` com placeholders para futuros módulos, `tests/`, `scripts/`, `alembic/`.
- [x] `.gitignore` cobre artefatos Python, `.env`, `__pycache__`, etc.
- [x] Teste automatizado do endpoint `/health` passa.

## Comments

- 2026-09-29: critérios já atendidos pelo commit `e317607` (bootstrap). Verificado: `uv run pytest` (102 passed, incluindo `tests/test_health.py` com casos 200 e 503), `docker compose up app` responde `GET /health` com `{"status":"ok","db":"ok"}` 200, e a extensão `vector` está ativa no Postgres 16 (`scripts/db-init/01-extensions.sql`).
