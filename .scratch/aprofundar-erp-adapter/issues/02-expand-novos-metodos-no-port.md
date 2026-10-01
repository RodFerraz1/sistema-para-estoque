# 02: Expand - novos métodos deep no port

**Status:** done
**Blocked by:** 01 (DTOs de domínio novos)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

O `ERPAdapter` (Protocol) passa a expor 7 métodos novos com vocabulário de domínio, `sku_code` como chave (exceto `carregar_fornecedor`, que segue por UUID), retornando DTOs de domínio direto. Os 7 métodos antigos (`get_sku_raw`, `list_skus_raw`, etc) **continuam existindo intactos** - isto é a fase _expand_ do expand-contract. `PostgresERPAdapter` implementa os novos com filtro (`WHERE ativo = true`) e ordenação (`ORDER BY preco_unitario_atual`) em SQL. `InMemoryERPAdapter` implementa os novos aplicando os mesmos filtro e ordenação em Python sobre suas listas. Nenhum caller usa os métodos novos ainda; um desenvolvedor rodando `pytest` deve ver testes específicos exercitando cada método novo tanto no adapter Postgres quanto no in-memory.

## Acceptance criteria

- [ ] `carregar_sku(sku_code: str) -> SKU | None` no Protocol, no Postgres e no InMemory.
- [ ] `listar_skus() -> list[SKU]` no Protocol, no Postgres e no InMemory.
- [ ] `carregar_fornecedor(fornecedor_id: UUID) -> Fornecedor | None` no Protocol, no Postgres e no InMemory.
- [ ] `fornecedores_de(sku_code: str) -> list[FornecedorParaSKU]` no Protocol, no Postgres e no InMemory - devolve **só fornecedores ativos**, ordenados por `preco_unitario_atual` ascendente.
- [ ] `estoque_de(sku_code: str) -> Estoque | None` no Protocol, no Postgres e no InMemory.
- [ ] `vendas_de(sku_code: str, desde: datetime) -> list[Venda]` no Protocol, no Postgres e no InMemory.
- [ ] `movimentacoes_de(sku_code: str, desde: datetime) -> list[Movimentacao]` no Protocol, no Postgres e no InMemory.
- [ ] `PostgresERPAdapter`: filtro `ativo=true` e ordenação por preço em `fornecedores_de` acontecem **no SQL**, não em Python.
- [ ] Testes novos em `src/erp_adapter/tests/`: pelo menos um teste por método novo, cobrindo caso feliz + edge (SKU inexistente, lista vazia, filtro corta inativos, ordem correta).
- [ ] Os 7 métodos antigos continuam existindo e passando nos testes antigos.
- [ ] `uv run pytest` verde.
