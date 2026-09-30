# 05: Migrate - `sales` usa novo port

**Status:** done
**Blocked by:** 02 (Expand - novos métodos deep no port)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

O módulo `sales` passa a operar em `sku_code`. `sales.service` chama `erp.vendas_de(sku_code, desde)` para giro, histórico e sazonalidade. Handler `/analise`, `/skus/{sku_code}/vendas` e `/skus/{sku_code}/sazonalidade` passam `sku_code` direto pro sales. Testes de `sales` adaptados às novas assinaturas; asserções sobre comportamento (giro correto, série mensal correta, sazonalidade neutra pra SKU sem vendas) não mudam.

## Acceptance criteria

- [ ] `sales.service.Sales` aceita `sku_code` como chave nos métodos públicos onde antes aceitava UUID.
- [ ] `sales.service` não chama mais nenhum método `*_raw` do adapter.
- [ ] `giro_medio_mensal`, `historico_vendas` e `sazonalidade` continuam produzindo o mesmo resultado.
- [ ] Handler `/analise`, `/skus/{sku_code}/vendas` e `/skus/{sku_code}/sazonalidade` usam a nova interface do sales.
- [ ] `src/sales/tests/test_sales.py` adaptado; asserções sobre comportamento não mudam.
- [ ] `src/api/tests/test_skus.py` e `tests/smoke/test_endpoints.py` passam sem alteração de asserção.
- [ ] Métodos antigos do port continuam existindo.
- [ ] `uv run pytest` verde.

## Dívida transitória deixada pelo ticket 04

- `Inventory.cobertura_meses(sku_code)` chama `erp.carregar_sku` só para obter `sku.id` e passar para `sales.giro_medio_mensal`. Com sales em `sku_code`, essa busca some e `_cobertura(sku: SKU)` volta a receber `sku_code`.
