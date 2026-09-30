# 07: Módulo `ficha_sku` + wire up `/analise` + CONTEXT.md

**Status:** done
**Blocked by:** 03 (Migrate catalog), 04 (Migrate inventory), 05 (Migrate sales)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

Nasce o módulo `src/ficha_sku/` que absorve a composição hoje presa dentro do handler `/analise`. Um método público: `FichaSKU.completa(sku_code) -> Ficha | None`. `Ficha` é um DTO Pydantic de domínio composto por `sku: SKU`, `estoque: Estoque`, `giro: Giro`, `cobertura: Cobertura`, `fornecedores: list[FornecedorParaSKU]`. `FichaSKU` recebe `Catalog`, `Inventory` e `Sales` via construtor (padrão dos outros módulos). Handler `/analise` passa a ter ~3 linhas: chama `ficha_sku.completa(sku_code)`, trata `None` como 404, projeta em `AnaliseSKUResponse` e retorna. Endpoints `/vendas`, `/sazonalidade`, `/fornecedores`, `/abaixo-do-piso` **não mudam** - ficha_sku só cobre o `/analise`. `CONTEXT.md` ganha o termo "Ficha (do SKU)" na seção Métricas ou Sistemas.

## Acceptance criteria

- [ ] Estrutura criada: `src/ficha_sku/__init__.py`, `schemas.py` (com `Ficha`), `service.py` (com `FichaSKU`), `dependencies.py` (com `get_ficha_sku`), `tests/__init__.py`, `tests/test_ficha_sku.py`.
- [ ] `Ficha` é frozen Pydantic, contém `sku: SKU`, `estoque: Estoque`, `giro: Giro`, `cobertura: Cobertura`, `fornecedores: list[FornecedorParaSKU]`.
- [ ] `FichaSKU.completa(sku_code)` retorna `Ficha | None`; devolve `None` se o SKU não existir.
- [ ] Handler `/analise` em `src/api/skus.py`: recebe `FichaSKU` via `Depends`, chama `completa`, trata `None` como 404, projeta pra `AnaliseSKUResponse`. Sem `Depends(get_catalog)`, `Depends(get_inventory)` ou `Depends(get_sales)` no handler.
- [ ] `src/ficha_sku/tests/test_ficha_sku.py` cobre pelo menos: caso feliz, SKU inexistente (retorna `None`), SKU sem vendas (`Ficha.cobertura.sem_giro=True`, `fornecedores=[]`).
- [ ] `src/api/tests/test_skus.py` (testes de `/analise`) passa **sem alteração de asserção**.
- [ ] `tests/smoke/test_endpoints.py` passa sem alteração.
- [ ] `CONTEXT.md` ganha entrada "**Ficha (do SKU)**" com definição e _Avoid_.
- [ ] `uv run pytest` verde.
