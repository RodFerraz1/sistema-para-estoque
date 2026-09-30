# 01: Prefactor - DTOs de domínio novos

**Status:** done
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/aprofundar-erp-adapter/spec.md`

## What to build

Prepara o terreno pra receber a nova interface do `ERPAdapter`. Cria os DTOs Pydantic de domínio que hoje não existem (`Fornecedor`, `Movimentacao`, `Venda`), cada um vivendo no módulo que possui o conceito. Nenhum código passa a usar essas classes ainda - o ticket entrega ferramenta, não comportamento. Um desenvolvedor abrindo `catalog/schemas.py`, `inventory/schemas.py` e `sales/schemas.py` depois deste ticket vê os DTOs novos ao lado dos existentes, com formato compatível com o que o adapter vai devolver depois.

## Acceptance criteria

- [ ] `Fornecedor` (Pydantic frozen) adicionado a `src/catalog/schemas.py`, com os campos hoje presentes em `FornecedorRaw` (id, nome, cnpj, prazo_pagamento_padrao, pedido_minimo_reais, lead_time_dias_contratado, ativo).
- [ ] `Movimentacao` (Pydantic frozen) adicionado a `src/inventory/schemas.py`, com os campos hoje presentes em `MovimentacaoRaw`.
- [ ] `Venda` (Pydantic frozen) adicionado a `src/sales/schemas.py`, com os campos hoje presentes em `VendaRaw`.
- [ ] Se `SKU` (em `catalog/schemas.py`) faltar algum campo hoje presente em `SKURaw`, adicioná-lo agora.
- [ ] Nenhum código de produção importa as classes novas ainda.
- [ ] `uv run pytest` continua verde (75+ testes).
- [ ] Nenhuma remoção de código nesta etapa.
