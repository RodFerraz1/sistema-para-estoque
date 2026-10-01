# 02: Estoque em trânsito

**Status:** done
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/sugestao-compra/spec.md`

## What to build

O `inventory` passa a saber quanto de um SKU está em trânsito, ou seja, o que falta chegar de pedidos de compra abertos. O `ERPAdapter` ganha `itens_em_transito_de(sku_code)`, e o `Inventory` ganha `em_transito(sku_code)`. A cobertura do M2 não muda. Nenhum endpoint novo: quem vai consumir isso é a sugestão (ticket 03).

## Acceptance criteria

- [ ] DTO `ItemEmTransito` em `src/inventory/schemas.py`: `pedido_id`, `fornecedor_id`, `status`, `quantidade_pendente`, `data_prevista_entrega`.
- [ ] DTO `EmTransito` com `total_unidades` e `itens`.
- [ ] `ERPAdapter.itens_em_transito_de(sku_code) -> list[ItemEmTransito]` no Protocol, no Postgres (filtro no SQL) e no InMemory.
- [ ] Considera só pedidos `aprovado`, `enviado` e `recebido_parcial`. `quantidade_pendente = quantidade - quantidade_recebida`. Itens com pendente 0 ficam de fora.
- [ ] `Inventory.em_transito(sku_code) -> EmTransito`. SKU sem pedidos abertos devolve `total_unidades = 0`.
- [ ] `Inventory.cobertura_meses` continua igual (só `quantidade_disponivel`).
- [ ] `InMemoryERPAdapter` aceita pedidos e itens na construção, e `tests/fakes.py` ganha builders para eles.
- [ ] Testes: cada status que conta e que não conta, `recebido_parcial` contando só o pendente, SKU sem pedidos, integração Postgres do método novo contra o seed.
- [ ] `uv run pytest` verde.
