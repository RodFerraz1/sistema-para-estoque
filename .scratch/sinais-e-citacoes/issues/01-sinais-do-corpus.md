# 01: Sinais do corpus para a sugestão de pedido

**Status:** ready-for-agent
**Blocked by:** M5 concluído
**Spec:** `.scratch/sinais-e-citacoes/spec.md` (seção "Sinais do corpus" e "Endpoint")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Para o fornecedor e o produto de uma sugestão de pedido, o código busca no corpus e pergunta ao Jev, trecho a trecho, se há relato de atraso do fornecedor, de venda forte por época e de encalhe. As respostas acima do limiar viram sinais com os trechos de origem, sem mexer na quantidade. Os limiares saem de uma avaliação contra o Jev real. `GET /skus/{sku_code}/sugestao-compra/sinais` expõe os sinais.

## Acceptance criteria

- [ ] `DecisionModel.avaliar_sinais` com as três perguntas da spec, no `JevDecisionModel` e no `InMemoryDecisionModel`.
- [ ] `BuscaContexto.buscar` com `com_conflitos` (padrão `True`).
- [ ] `src/ai/sinais.py`: `SinaisCorpus.para_sugestao` e `para_sugestoes` (um cálculo por par fornecedor e produto), `K_SINAIS`, `MAX_TRECHOS_SINAIS`, `LIMIARES_SINAIS`; `SinalCorpus`, `ProdutoDoSinal`, `AvaliacaoSinais` e `SugestaoComSinais` nos schemas.
- [ ] `evals/sinais.json` rotulado antes de rodar; `scripts/avaliar_sinais.py` (com `--de-arquivo`) rodado contra o Jev real; respostas cruas em `evals/resultados/`; resultado e limiares escolhidos num comentário deste ticket. O teste que confere os ids de `evals/` cobre o arquivo novo.
- [ ] `GET /skus/{sku_code}/sugestao-compra/sinais` (404, 503, lista vazia sem fornecedor).
- [ ] Testes da spec e um `externo` do `avaliar_sinais`.
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
