# 09: Entregas atrasadas e cobrança de entrega

**What to build:** o comprador chefe vê no painel as entregas atrasadas, agrupadas por fornecedor, com os pedidos, os SKUs, a quantidade que falta e os dias de atraso, primeiro os fornecedores com SKU em ruptura. Ele registra que cobrou o fornecedor, com nova previsão opcional, e o pedido sai do painel até essa data (ou por 7 dias). Se a previsão vencer sem a mercadoria, o pedido volta. A tela do SKU mostra as entregas pendentes e as cobranças, e há um histórico de atrasos por fornecedor.

**Blocked by:** 04, 06

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Entregas atrasadas e cobrança")

- [ ] `inventory.entregas_atrasadas(agora)` a partir do retrato: status `aprovado`, `enviado` ou `recebido_parcial`, pendente maior que zero e data prevista anterior a hoje. Sem data prevista, nunca atrasada.
- [ ] `MotivoAlerta`/`TipoAlerta` ganham `entrega_atrasada`. Migration: a versão padrão da política passa a incluí-lo. A tela de política mostra a caixa nova.
- [ ] Tabela `cobrancas_entrega` no schema `copilot`, com `usuario_id`. Cobrança vigente: a mais recente do pedido, até `nova_previsao` ou por `PRAZO_DA_COBRANCA` (7 dias).
- [ ] `GET /painel` ganha `entregas_atrasadas` (fornecedores, pedidos e SKUs) e o filtro `motivo=entrega_atrasada`. `POST /pedidos/{id}/cobrancas` e `GET /fornecedores/{id}/atrasos`.
- [ ] UI: grupo "Entregas atrasadas" no painel com o botão "Cobrei o fornecedor" (nova previsão e comentário), e bloco de entregas pendentes na tela do SKU.
- [ ] Testes HTTP com relógio injetado: data ontem entra, hoje não, sem data nunca, `recebido_total` nunca, a cobrança tira até a nova previsão, a previsão vencida traz de volta, e o fornecedor com SKU em ruptura vem primeiro. Contrato do repositório em memória e no Postgres.
- [ ] Verificado no navegador com o cenário do pedido atrasado do seed. Typecheck e suíte completa verdes.
