# Schema do ERP fake

Proposta de modelagem relacional pro ERP simulado. Este documento é o *contrato* que o Copilot vai enxergar quando pedir dados via `erp_adapter`. Se você vier a plugar num ERP real depois, o adapter converte da estrutura real pra esta - por isso vale desenhar bem agora.

## Princípios

1. **Separação clara entre catálogo, movimentação e pedidos**. Catálogo é dado mestre. Estoque/vendas são fatos observados. Pedidos são intenções (podem ou não virar fatos).
2. **Movimentação como append-only ledger**, não como coluna mutável. Isso é como ERPs sérios fazem e vai ser útil pra Copilot conseguir explicar "por que o estoque está assim".
3. **SKU é a entidade central** de tudo. Produto é agrupador; SKU é o que gira.
4. **Um SKU pode ter vários fornecedores**, com preços e condições diferentes. Relação N:N via tabela de junção.

## Tabelas

### `produtos`

Grupo conceitual. "Toalha Banho Conforto" é um produto; suas variações de cor/tamanho são SKUs.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| nome | text | "Toalha Banho Conforto" |
| categoria | text | "felpudo", "jogo_cama", "mesa", "cozinha" |
| descricao | text | livre |
| ativo | bool | soft delete |
| criado_em | timestamp | |

### `skus`

Unidade real de estoque e venda.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| produto_id | uuid FK → produtos | |
| sku_code | text unique | ex: "TBC-BEG-70140" |
| cor | text | |
| tamanho | text | "70x140", "queen", "king" |
| gramatura | int nullable | g/m² quando aplicável |
| material | text nullable | "algodão 100%", "percal 200 fios" |
| ativo | bool | |
| criado_em | timestamp | |

### `fornecedores`

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| nome | text | "Katrina Têxtil" |
| cnpj | text | pode ser fictício |
| prazo_pagamento_padrao | text | "30/60/90" |
| pedido_minimo_reais | int | em centavos ou reais inteiros, escolher |
| lead_time_dias_contratado | int | prometido |
| ativo | bool | |
| criado_em | timestamp | |

### `fornecedores_skus`

Junção N:N. Qual fornecedor supre qual SKU, sob quais condições.

| coluna | tipo | notas |
|---|---|---|
| fornecedor_id | uuid FK | PK composta |
| sku_id | uuid FK | PK composta |
| preco_unitario_atual | int | centavos |
| moq_unidades | int | mínimo por SKU pra esse fornecedor |
| lead_time_dias_observado | int nullable | média histórica real, populada por batch |
| ativo | bool | |
| atualizado_em | timestamp | |

### `estoque_snapshot`

Fotografia atual. Não é fonte da verdade sozinha - deve poder ser reconstruída a partir de `movimentacoes_estoque`. Existe pra query rápida.

| coluna | tipo | notas |
|---|---|---|
| sku_id | uuid PK FK | |
| quantidade_disponivel | int | |
| quantidade_reservada | int | reservada pra pedidos em aberto |
| atualizado_em | timestamp | |

### `movimentacoes_estoque`

Ledger append-only. Fonte da verdade.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| sku_id | uuid FK | |
| tipo | enum | `entrada_compra`, `saida_venda`, `ajuste_positivo`, `ajuste_negativo`, `devolucao` |
| quantidade | int | sempre positivo, o `tipo` diz a direção |
| data | timestamp | |
| referencia_tipo | text nullable | `pedido_compra`, `venda`, `ajuste_manual` |
| referencia_id | uuid nullable | id do documento origem |
| observacao | text nullable | |

### `vendas`

Fatos de venda ao varejista (cliente do atacadista). Base pra cálculo de giro.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| sku_id | uuid FK | |
| quantidade | int | |
| valor_unitario_reais | int | centavos |
| data | timestamp | |
| cliente_ref | text | id fictício do cliente varejista, não modelamos entidade cliente agora |

### `pedidos_compra`

Header do pedido de compra do atacadista pro fornecedor.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| fornecedor_id | uuid FK | |
| status | enum | `rascunho`, `aprovado`, `enviado`, `recebido_parcial`, `recebido_total`, `cancelado` |
| criado_em | timestamp | |
| aprovado_em | timestamp nullable | |
| enviado_em | timestamp nullable | |
| recebido_em | timestamp nullable | |
| data_prevista_entrega | date nullable | |
| valor_total_reais | int | centavos |
| observacao | text nullable | |

### `pedidos_compra_itens`

Linhas do pedido.

| coluna | tipo | notas |
|---|---|---|
| id | uuid PK | |
| pedido_id | uuid FK | |
| sku_id | uuid FK | |
| quantidade | int | |
| preco_unitario_reais | int | centavos |
| quantidade_recebida | int default 0 | atualiza em recebimentos parciais |

## Fora de escopo agora

- Clientes do atacadista (varejistas) como entidade. `cliente_ref` é string opaca.
- Notas fiscais, impostos, tributação.
- Múltiplos CDs / localização física de estoque.
- Devoluções ao fornecedor.
- Auditoria de mudança em dados mestres.

Se algum desses virar necessário, ADR novo antes de mexer no schema.

## Volume sintético a gerar (seed script)

Alvo pro seed inicial:

- ~15 produtos, ~80 SKUs
- 5 fornecedores (os 3 do corpus + 2 secundários)
- ~180 relações fornecedor-SKU
- Estoque snapshot pra todos os SKUs
- ~2 anos de movimentações e vendas com sazonalidade plausível (spike Natal, dia das mães)
- ~15 pedidos de compra em vários estados (recebido, em trânsito, rascunho)

Volume pequeno de propósito: cabe em memória, roda rápido no dev, mas grande o suficiente pra que `giro` e `cobertura` sejam significativos.
