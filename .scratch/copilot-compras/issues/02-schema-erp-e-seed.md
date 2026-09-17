# 02: Schema `erp` e seed reproduzível

**Status:** ready-for-agent
**Blocked by:** 01 (Fundação técnica)
**Spec:** `.scratch/copilot-compras/spec.md`
**Schema:** `.scratch/copilot-compras/erp-schema.md`

## What to build

O ERP fake existe como schema no Postgres com as 9 tabelas definidas em `erp-schema.md`, e um script de seed popula dados sintéticos reprodutíveis simulando 2 anos de operação do atacadista de cama, mesa e banho. Rodar o seed duas vezes produz exatamente o mesmo estado. Após rodar o seed, um desenvolvedor consegue confirmar via `psql` (ou consulta direta) que os SKUs, fornecedores, vendas e movimentações esperadas estão populados.

## Acceptance criteria

- [ ] Alembic configurado com migrations versionadas. `alembic upgrade head` cria os schemas `erp` e `copilot` (este vazio) e todas as 9 tabelas do schema `erp` conforme `erp-schema.md`.
- [ ] Constraints, chaves e enums do schema estão corretos (movimentacao tipo, pedido_compra status, PKs compostas em `fornecedores_skus`).
- [ ] Script `scripts/seed.py` executável via `uv run python -m scripts.seed`, com semente fixa (`random.seed(42)`) garantindo reprodutibilidade.
- [ ] Seed popula: ~15 produtos distribuídos em `felpudo`, `jogo_cama`, `mesa`, `cozinha`; ~80 SKUs (variações cor/tamanho/gramatura); 5 fornecedores incluindo Katrina Têxtil, Verdela Home e Malha Fina (nomes casam com o corpus RAG em `rag-seeds/fornecedores/`); ~180 relações fornecedor-SKU com preços plausíveis.
- [ ] 2 anos (24 meses) de movimentações e vendas com padrão sazonal plausível: spike em nov-dez, bump em maio, dip em fev-mar. `estoque_snapshot` coerente com esse histórico e com cobertura entre 0.5 e 4 meses (variedade de casos).
- [ ] 15 pedidos de compra em estados variados (`recebido_total`, `enviado`, `rascunho`, etc).
- [ ] Seed é **idempotente**: rodar duas vezes seguidas resulta no mesmo estado final (limpa e repopula).
- [ ] Teste smoke verifica contagens esperadas por tabela e sanidade dos dados (ex: nenhum SKU com giro negativo, todas as relações fornecedor-SKU apontam para IDs válidos).
