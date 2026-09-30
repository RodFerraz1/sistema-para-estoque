# 03: Migrate - `catalog` usa novo port

**Status:** done
**Blocked by:** 02 (Expand - novos métodos deep no port)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

O módulo `catalog` para de fazer a dança `código → UUID → resto`. `catalog.service` chama `erp.carregar_sku(sku_code)` e `erp.fornecedores_de(sku_code)` direto. O método `buscar_sku_por_codigo` deixa de existir (ou vira delegação trivial de uma linha) porque perdeu razão de ser - o adapter já resolve por código. As partes do handler `/analise`, `/skus/{sku_code}/fornecedores` e outros endpoints que hoje passam por `catalog.buscar_sku_por_codigo` passam a chamar a nova interface. Comportamento HTTP idêntico. Testes de HTTP não mudam de asserção. Testes unitários de `catalog` são adaptados às novas assinaturas.

## Acceptance criteria

- [ ] `catalog.service.Catalog` expõe métodos que aceitam `sku_code` diretamente onde antes aceitavam UUID (ou deixa clara a nova assinatura mínima que os consumidores precisam).
- [ ] `catalog.buscar_sku_por_codigo` some, ou vira delegação trivial pra `erp.carregar_sku`.
- [ ] `catalog.service` não chama mais nenhum método `*_raw` do adapter.
- [ ] Handler `/analise` e demais endpoints do `src/api/skus.py` que hoje chamam `catalog.buscar_sku_por_codigo` passam a chamar a nova interface do catalog (sem a dança code→UUID).
- [ ] `src/catalog/tests/test_catalog.py` adaptado às novas assinaturas; asserções sobre comportamento não mudam.
- [ ] `src/api/tests/test_skus.py` passa sem alteração de asserção.
- [ ] `tests/smoke/test_endpoints.py` passa sem alteração.
- [ ] Métodos antigos do port continuam existindo (contract deletion é ticket 06).
- [ ] `uv run pytest` verde.
