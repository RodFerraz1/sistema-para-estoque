# 04: Endpoints de leitura complementares

**Status:** shipped
**Blocked by:** 03 (Análise de SKU end-to-end)
**Spec:** `.scratch/copilot-compras/spec.md`

## What to build

O comprador chefe consegue: listar SKUs abaixo do piso de estoque pra priorizar reposição, consultar o histórico de vendas mensais de um SKU pra entender tendência, ver a sazonalidade de um SKU (multiplicadores mês-a-mês) pra ajustar decisões, e listar todos os fornecedores de um SKU com condições comerciais completas pra escolher onde comprar.

## Acceptance criteria

- [x] `GET /skus/abaixo-do-piso?dias=20` retorna lista de SKUs com cobertura abaixo do piso (padrão 20 dias, parametrizável). Cada item inclui `sku_code`, nome, cobertura em meses.
- [x] `Inventory.abaixo_do_piso(dias_piso)` implementado convertendo dias para meses (`dias_piso / 30`) e comparando com cobertura de cada SKU.
- [x] `GET /skus/{sku_code}/vendas?meses=12` retorna série mensal de vendas (mês + quantidade + valor total) pra janela solicitada.
- [x] `Sales.historico_vendas(sku_id, meses)` implementado.
- [x] `GET /skus/{sku_code}/sazonalidade` retorna dict `{mes: multiplicador}` com 12 entradas, calculado conforme regra do spec (média das vendas naquele mês nos últimos 24 meses / média geral do período).
- [x] `Sales.sazonalidade(sku_id)` implementado.
- [x] `GET /skus/{sku_code}/fornecedores` retorna lista de fornecedores que suprem o SKU, cada um com nome, preço unitário atual, MOQ, lead time contratado, lead time observado, prazo de pagamento, pedido mínimo do fornecedor.
- [x] Cada endpoint tem pelo menos 1 teste feliz e 1 edge case (SKU inexistente, SKU sem vendas suficientes pra sazonalidade, lista abaixo-do-piso vazia).
- [x] Endpoints reutilizam a mesma injeção de `erp_adapter` estabelecida no ticket 03.
