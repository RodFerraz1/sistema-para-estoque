## Agent skills

### Issue tracker

Issues live as local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### IA (módulo `ai`)

Segue a ADR-0002: Jev decide, código executa, LLM redige. Antes de mexer em `ai`, ler `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`. Referência da API do Jev: https://docs.typesafe.ai/llms.txt (limites conhecidos em `model-jaggedness/jev-1.13.md`).
