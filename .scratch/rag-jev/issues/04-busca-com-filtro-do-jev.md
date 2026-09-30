# 04: Busca com filtro do Jev end-to-end

**Status:** blocked (gate da ADR-0002 não passou; aguarda decisão do dev sobre a ADR)
**Blocked by:** 02 (Spike do Jev, precisa ter passado no gate), 03 (Ingestão do corpus no pgvector)
**Spec:** `.scratch/rag-jev/spec.md`
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O comprador pesquisa em `GET /rag/busca?q=...&k=...` e recebe os trechos mais parecidos, cada um classificado como `aceito`, `conflitante` ou `descartado` a partir das quatro respostas do Jev e dos limiares do spike. O Jev entra atrás do port `DecisionModel`, com um adapter in-memory para os testes. Conflito entre trechos fica para o 05.

## Acceptance criteria

- [ ] Port `DecisionModel` com `avaliar_trechos(pergunta, trechos) -> list[AvaliacaoTrecho]` e a exceção `DecisaoIndisponivel`.
- [ ] `JevDecisionModel` com as quatro perguntas da spec, na redação escolhida no spike, um request por trecho, até 8 em paralelo. `modelo` vem da resposta. Erro do SDK depois das retentativas vira `DecisaoIndisponivel`.
- [ ] `JEV_MODEL` com padrão `jev-1.13.0` em `Settings` e `.env.example`.
- [ ] `InMemoryDecisionModel` configurável por trecho, com padrão e com modo de falha.
- [ ] `BuscaContexto.buscar(pergunta, k)` com `LIMIARES` (valores do `spike-resultado.md`) e a classificação na ordem da spec. `ResultadoBusca` ordenado por classificação e depois por similaridade, com `conflitos` vazio por enquanto.
- [ ] `GET /rag/busca`: 422 para `q` vazio ou acima de 500 caracteres e para `k` fora de 1 a 40 (padrão 30, decisão do ticket 03); 503 para `DecisaoIndisponivel`; 200 com listas vazias quando o corpus não foi ingerido.
- [ ] Testes: uma regra de classificação por teste, precedência das regras, valores no limiar, falha do Jev (com `InMemoryDecisionModel`); `JevDecisionModel` com cliente TypeSafe falso (state, mapeamento das respostas, `modelo`, erro); teste `externo` contra o Jev real, pulado sem `JEV_KEY`; HTTP feliz, 422, 503 e corpus vazio.
- [ ] Marcador `externo` registrado no `pyproject.toml`.
- [ ] `uv run pytest` verde.

## Comments

**2026-09-30 (agente):** bloqueado pelo resultado do spike (`.scratch/rag-jev/spike-resultado.md`). O ticket 03 mudou o `k` padrão da busca para 30 (recall@30 de 0,92), então o endpoint aceita `k` de 1 a 40.
