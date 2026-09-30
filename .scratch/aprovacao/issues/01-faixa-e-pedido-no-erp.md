# 01: Faixa de aprovação e pedido de compra no ERP fake

**Status:** ready-for-agent
**Blocked by:** M6 concluído
**Spec:** `.scratch/aprovacao/spec.md` (seções "Faixa de aprovação" e "Escrita no ERP fake")
**ADR:** `docs/adr/0003-politica-de-compra-configuravel.md`

## What to build

A política de compra ganha os limites das faixas de aprovação, e o `purchasing` calcula a faixa de um pedido com as exceções do documento de aprovação. O `ERPAdapter` ganha a única escrita do Copilot no ERP: criar pedido de compra `aprovado`, chamado por `purchasing.submeter_pedido`.

## Acceptance criteria

- [ ] `faixa_1_ate_reais`, `faixa_2_ate_reais`, `faixa_3_ate_reais` em `ParametrosPolitica` (com validação de ordem), migration `0006` com os padrões do documento, `GET/PUT /politica-compra` com os campos.
- [ ] `purchasing.faixa_aprovacao` e `FaixaAprovacao` com as regras da spec.
- [ ] `ERPAdapter.criar_pedido_compra`, `ItemNovoPedido` e `ERPAdapter.fornecedor_tem_pedido`, em Postgres e in-memory, com teste de contrato.
- [ ] `purchasing.submeter_pedido` com as validações, a data prevista e a observação da spec.
- [ ] Testes da spec.
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
