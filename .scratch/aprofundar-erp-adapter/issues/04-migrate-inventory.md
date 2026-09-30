# 04: Migrate - `inventory` usa novo port

**Status:** done
**Blocked by:** 02 (Expand - novos métodos deep no port)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

O módulo `inventory` passa a operar em `sku_code`. `inventory.service` chama `erp.estoque_de(sku_code)` e `erp.movimentacoes_de(sku_code, desde)`. Handler `/analise` e endpoints relacionados a estoque/movimentações passam `sku_code` pro inventory. `inventory.abaixo_do_piso` continua onde está (respeita ADR-0001: cálculo depende de giro, que é `sales`), mas seus consumos do adapter migram pra nova interface. Testes de `inventory` adaptados às novas assinaturas; asserções sobre comportamento não mudam.

## Acceptance criteria

- [ ] `inventory.service.Inventory` aceita `sku_code` como chave nos métodos públicos onde antes aceitava UUID.
- [ ] `inventory.service` não chama mais nenhum método `*_raw` do adapter.
- [ ] `inventory.abaixo_do_piso` continua produzindo o mesmo resultado (mesmo shape de `SKUAbaixoDoPiso`); internamente usa os métodos novos.
- [ ] Handler `/analise`, `/skus/{sku_code}/abaixo-do-piso` e demais endpoints que passam por inventory usam a nova interface.
- [ ] `src/inventory/tests/test_inventory.py` adaptado; asserções sobre comportamento não mudam.
- [ ] `src/api/tests/test_skus.py` e `tests/smoke/test_endpoints.py` passam sem alteração de asserção.
- [ ] Métodos antigos do port continuam existindo.
- [ ] `uv run pytest` verde.
