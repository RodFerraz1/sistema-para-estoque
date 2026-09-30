# 06: Contract - deletar métodos e DTOs `*Raw` antigos

**Status:** done
**Blocked by:** 03 (Migrate catalog), 04 (Migrate inventory), 05 (Migrate sales)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

Fase _contract_ do expand-contract: apaga o código morto agora que nada mais depende dele. Os 7 métodos antigos (`get_sku_raw`, `list_skus_raw`, `get_fornecedor_raw`, `list_fornecedores_para_sku` na forma antiga com sufixo `_raw` de retorno, `get_estoque_atual`, `list_movimentacoes`, `list_vendas`) desaparecem do Protocol, do `PostgresERPAdapter` e do `InMemoryERPAdapter`. O arquivo `src/erp_adapter/schemas.py` (que contém os `*Raw` e o `FiltrosSKU`) é deletado - ou fica vazio. `tests/fakes.py` é reescrito: os builders (`make_sku`, `make_fornecedor`, `make_fornecedor_sku`, `make_estoque`, `make_venda`, `make_movimentacao`) passam a construir DTOs de domínio (`SKU`, `Fornecedor`, `FornecedorParaSKU`, `Estoque`, `Venda`, `Movimentacao`) diretamente. `InMemoryERPAdapter.__init__` passa a receber essas listas de domínio. Verificável por grep: zero import de qualquer classe `*Raw` no repositório.

## Acceptance criteria

- [ ] Os 7 métodos antigos removidos do Protocol `ERPAdapter`.
- [ ] Suas implementações removidas de `PostgresERPAdapter` e `InMemoryERPAdapter`.
- [ ] `src/erp_adapter/schemas.py` deletado (ou esvaziado, se necessário manter o arquivo).
- [ ] `tests/fakes.py` reescrito: builders devolvem DTOs de domínio.
- [ ] `InMemoryERPAdapter.__init__` aceita listas de DTOs de domínio.
- [ ] `grep -r "Raw" src/` não devolve nenhuma classe/tipo `*Raw` (apenas ocorrências não relacionadas, se houver).
- [ ] Testes antigos que exercitavam métodos `*_raw` são deletados (o comportamento equivalente já é coberto pelos testes dos métodos novos criados em 02).
- [ ] `uv run pytest` verde (75+ testes, incluindo smoke se DB disponível).

## Notas de implementação

- `Estoque` e `FornecedorParaSKU` não carregam o SKU, então `InMemoryERPAdapter` recebe `estoques: dict[str, Estoque]` e `fornecedores_por_sku: dict[str, list[FornecedorParaSKU]]`, indexados por `sku_code`, em vez de listas.
- Vínculo fornecedor-SKU inativo não é representável no DTO de domínio: no in-memory ele é a ausência na lista. O filtro de vínculo inativo segue testado só no Postgres; o in-memory testa fornecedor inativo.
- `get_sku_raw_por_codigo` (não listado entre os 7) também foi removido.
