# 06: Retrato em lote do ERP e painel em escala

**What to build:** o painel abre em menos de 2 segundos com 5.000 SKUs ativos. Prefactor das telas seguintes: a porta do ERP ganha leituras em lote (um retrato do estoque inteiro) e o `purchasing` calcula as sugestões de todos os SKUs a partir do retrato, com a mesma conta da leitura de um SKU. O comprador não vê diferença, só velocidade.

**Blocked by:** 02, 05

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Escala: leitura em lote e filtros")

- [ ] A porta do ERP ganha `estoques()`, `giros(desde)` (soma por SKU e mês), `vendas_diarias(desde)` (soma por SKU e dia), `fornecedores_por_sku()` e `itens_em_transito()`, nas duas implementações.
- [ ] `purchasing.sugerir_pedidos(retrato)` e `sugerir_pedido(sku)` montando um retrato de um SKU só, para os dois caminhos usarem a mesma conta.
- [ ] O painel usa o retrato. O número de consultas ao banco não depende do número de SKUs (teste que conta as consultas com um listener do SQLAlchemy).
- [ ] Contrato das leituras em lote rodando contra o adapter em memória e o Postgres, e teste de que o retrato e a leitura por SKU dão a mesma sugestão de pedido para os mesmos dados.
- [ ] Script de benchmark com `--skus 5000` do seed, com o tempo de `GET /painel` registrado no ticket.
- [ ] Typecheck e suíte completa verdes.
