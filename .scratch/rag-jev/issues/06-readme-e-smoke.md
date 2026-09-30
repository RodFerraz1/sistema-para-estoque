# 06: README e smoke test do M4

**Status:** done
**Blocked by:** 05 (Conflito entre trechos), ou 04 se o 05 tiver sido cancelado
**Spec:** `.scratch/rag-jev/spec.md`

## What to build

O smoke test passa a cobrir a ingestão e a busca contra Postgres de verdade, e o README documenta o RAG e o papel do Jev.

## Acceptance criteria

- [x] `tests/smoke` ingere o `corpus/` com o `FastEmbedEmbedder` real depois das migrations e do seed. Uma segunda ingestão devolve tudo inalterado.
- [x] Smoke de `GET /rag/busca?q=lead time da Katrina`: com `JEV_KEY`, status 200, shape do DTO e pelo menos um trecho `aceito` de um documento da Katrina. Sem `JEV_KEY`, só esse teste é pulado.
- [x] README: como ingerir o corpus, `/rag/busca` na lista de endpoints com um exemplo de resposta, módulo `ai` no diagrama, variáveis novas de ambiente, e links para a ADR-0002, a ADR-0004 e o `spike-resultado.md`.
- [x] Roadmap: M4 marcado como concluído.
- [x] `uv run pytest` verde, incluindo smoke.

## Comments

**2026-09-30 (agente):** pronto. O smoke da busca também leva o marcador `externo`. O exemplo de resposta do README veio da busca real, cortado para 3 dos 30 trechos e 1 dos 6 conflitos.

Na busca real de "lead time da Katrina", 8 trechos saem `aceito`, e o conflito mais forte (0,63) é entre a ata do Natal 2024 (lead time de 68 dias em outubro-novembro) e as notas internas do contrato (45 dias cumpridos em setembro-outubro). O par da cláusula 3 do contrato com a revisão Q1/2025 não é comparado: esses dois trechos são o 7º e o 8º aceitos por similaridade, e o conflito só olha os 6 primeiros. Três dos 6 conflitos sinalizados ficam entre 0,11 e 0,15, perto do limiar de 0,10.

Com o smoke carregando o `FastEmbedEmbedder` real, o `uv run pytest` passou a terminar com SIGABRT (exit 134) em parte das execuções, mesmo com todos os testes verdes. A causa é a telemetria do onnxruntime 1.30: um envio em andamento na saída do processo trava um mutex já destruído. `src/ai/embeddings.py` define `ORT_DISABLE_TELEMETRY=1` antes de importar o fastembed, em commit separado.

