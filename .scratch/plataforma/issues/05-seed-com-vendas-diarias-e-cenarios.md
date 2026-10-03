# 05: Seed com vendas diárias e os cenários da reunião

**What to build:** o ERP fake passa a contar a história do comprador. O seed gera dados até a data em que roda, com vendas diárias nos últimos 90 dias (domingos fechados), e tem cenários fixos: o tapete marrom que vendia 10 por dia e parou com estoque, um SKU em ruptura sem pedido, um pedido enviado com data prevista vencida há 10 dias contendo um SKU em ruptura, e um SKU que parou de vender sem estoque. Um modo gera milhares de SKUs para medir escala.

**Blocked by:** 01

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Seed e dados de demonstração")

- [ ] `NOW` do seed é o dia em que ele roda. Mesmo dia, mesmo banco: o seed continua reprodutível e idempotente.
- [ ] Vendas diárias nos últimos 90 dias, uma linha por SKU e dia aberto, sem venda aos domingos. Antes disso continua o padrão mensal. A giro do mês corrente não cai mais por falta de dado.
- [ ] Produto "Tapete Banheiro", categoria `banho`, com a cor marrom, e os quatro cenários com códigos de SKU estáveis, documentados no topo do seed.
- [ ] O Tapete Banheiro tem 5 cores com participação nas vendas bem diferente (marrom perto de 45%, branco perto de 8%), para o mix de gôndola.
- [ ] `--skus N` gera N SKUs sintéticos a mais.
- [ ] O teste de smoke do seed confere os cenários (o tapete com estoque e venda recente baixa, o pedido com data vencida etc.).
- [ ] Painel, tela do SKU e chat continuam funcionando com o seed novo (verificado no navegador).
