# 02: Schema `erp` e seed reproduzível

**Status:** done
**Blocked by:** 01 (Fundação técnica)
**Spec:** `.scratch/copilot-compras/spec.md`
**Schema:** `.scratch/copilot-compras/erp-schema.md`

## What to build

O ERP fake existe como schema no Postgres com as 9 tabelas definidas em `erp-schema.md`, e um script de seed popula dados sintéticos reprodutíveis simulando 2 anos de operação do atacadista de cama, mesa e banho. Rodar o seed duas vezes produz exatamente o mesmo estado. Após rodar o seed, um desenvolvedor consegue confirmar via `psql` (ou consulta direta) que os SKUs, fornecedores, vendas e movimentações esperadas estão populados.

## Acceptance criteria

- [x] Alembic configurado com migrations versionadas. `alembic upgrade head` cria os schemas `erp` e `copilot` (este vazio) e todas as 9 tabelas do schema `erp` conforme `erp-schema.md`.
- [x] Constraints, chaves e enums do schema estão corretos (movimentacao tipo, pedido_compra status, PKs compostas em `fornecedores_skus`).
- [x] Script `scripts/seed.py` executável via `uv run python -m scripts.seed`, com semente fixa (`random.seed(42)`) garantindo reprodutibilidade.
- [x] Seed popula: ~15 produtos distribuídos em `felpudo`, `jogo_cama`, `mesa`, `cozinha`; ~80 SKUs (variações cor/tamanho/gramatura); 5 fornecedores incluindo Katrina Têxtil, Verdela Home e Malha Fina (nomes casam com o corpus RAG em `rag-seeds/fornecedores/`); ~180 relações fornecedor-SKU com preços plausíveis.
- [x] 2 anos (24 meses) de movimentações e vendas com padrão sazonal plausível: spike em nov-dez, bump em maio, dip em fev-mar. `estoque_snapshot` coerente com esse histórico e com cobertura entre 0.5 e 4 meses (variedade de casos).
- [x] 15 pedidos de compra em estados variados (`recebido_total`, `enviado`, `rascunho`, etc).
- [x] Seed é **idempotente**: rodar duas vezes seguidas resulta no mesmo estado final (limpa e repopula).
- [x] Teste smoke verifica contagens esperadas por tabela e sanidade dos dados (ex: nenhum SKU com giro negativo, todas as relações fornecedor-SKU apontam para IDs válidos).

## Comments

- 2026-09-29: critérios já atendidos pelo commit `e317607` (bootstrap). Verificado: `alembic upgrade head` em `0001_erp_schema` cria as 9 tabelas em `erp` e o schema `copilot`, com os enums `movimentacao_tipo` e `pedido_compra_status` conforme `erp-schema.md`. Duas execuções seguidas de `uv run python -m scripts.seed` produzem hash idêntico de `vendas`, `movimentacoes_estoque` e `pedidos_compra`. Volumes: 15 produtos, 80 SKUs, 5 fornecedores, 191 relações fornecedor-SKU e 15 pedidos em 6 status. Sazonalidade: pico em nov-dez, bump em maio e vale em fev-mar. Cobertura: 73 dos 80 SKUs entre 0.5 e 4 meses (mín 0.56, máx 5.04). `tests/test_seed_smoke.py`: 11 passed.
