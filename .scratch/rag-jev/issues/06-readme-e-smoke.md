# 06: README e smoke test do M4

**Status:** ready-for-agent
**Blocked by:** 05 (Conflito entre trechos), ou 04 se o 05 tiver sido cancelado
**Spec:** `.scratch/rag-jev/spec.md`

## What to build

O smoke test passa a cobrir a ingestão e a busca contra Postgres de verdade, e o README documenta o RAG e o papel do Jev.

## Acceptance criteria

- [ ] `tests/smoke` ingere o `corpus/` com o `FastEmbedEmbedder` real depois das migrations e do seed. Uma segunda ingestão devolve tudo inalterado.
- [ ] Smoke de `GET /rag/busca?q=lead time da Katrina`: com `JEV_KEY`, status 200, shape do DTO e pelo menos um trecho `aceito` de um documento da Katrina. Sem `JEV_KEY`, só esse teste é pulado.
- [ ] README: como ingerir o corpus, `/rag/busca` na lista de endpoints com um exemplo de resposta, módulo `ai` no diagrama, variáveis novas de ambiente, e links para a ADR-0002, a ADR-0004 e o `spike-resultado.md`.
- [ ] Roadmap: M4 marcado como concluído.
- [ ] `uv run pytest` verde, incluindo smoke.
