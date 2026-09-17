# 01: Fundação técnica

**Status:** ready-for-agent
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/copilot-compras/spec.md`

## What to build

Um desenvolvedor consegue clonar o repositório, rodar `docker compose up` e ter a aplicação FastAPI + Postgres com pgvector no ar. O endpoint `/health` responde 200 confirmando que app e banco estão saudáveis. Projeto Python configurado com `uv`, estrutura de diretórios inicial preparada pros módulos que virão nos próximos tickets.

## Acceptance criteria

- [ ] `pyproject.toml` configurado com `uv`, Python 3.12+, dependências mínimas (FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, psycopg).
- [ ] `docker-compose.yml` sobe Postgres 16 com extensão `pgvector` habilitada e a app FastAPI em container separado.
- [ ] `docker compose up` funciona a partir de repositório limpo, sem passos manuais adicionais.
- [ ] `GET /health` retorna `{"status": "ok", "db": "ok"}` com status 200 quando app e banco estão saudáveis.
- [ ] `GET /health` retorna status apropriado (não 200) quando o banco está inacessível.
- [ ] Estrutura de diretórios inicial: `src/` com placeholders para futuros módulos, `tests/`, `scripts/`, `alembic/`.
- [ ] `.gitignore` cobre artefatos Python, `.env`, `__pycache__`, etc.
- [ ] Teste automatizado do endpoint `/health` passa.
