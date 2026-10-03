# 13: Consulta da vendedora e Meus avisos

**What to build:** a vendedora busca um SKU no celular e vê se tem estoque, se vem compra e quando chega ("chega por volta de 15/10", ou "atrasada"), sem preço de compra nem fornecedor. Ela ganha a lista "Meus avisos", com o que o comprador decidiu sobre cada aviso, e é notificada quando ele decide.

**Blocked by:** 09, 10

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Consulta e acompanhamento da vendedora")

- [ ] `GET /skus/{sku_code}/disponibilidade` (papéis `vendas`, `reposicao` e `comprador`): disponível, situação `tem | pouco | acabou` e entregas pendentes com previsão (a nova previsão da cobrança, quando houver) e `atrasada`.
- [ ] `GET /avisos/meus`: os avisos do usuário nos últimos 30 dias, cada um com a decisão de compra que o fechou ou "aguardando o comprador".
- [ ] Decisão de compra que fecha avisos abre episódios `decisao_sobre_aviso` dirigidos à vendedora de cada aviso.
- [ ] A página da equipe de vendas tem a busca com a disponibilidade no resultado, o botão "avisar o comprador" e "Meus avisos", continuando simples no celular.
- [ ] Testes HTTP: nenhuma rota que a vendedora pode chamar devolve preço de compra ou fornecedor, a previsão usa a cobrança quando há, "Meus avisos" mostra só os da própria vendedora, e a decisão notifica a autora do aviso.
- [ ] Verificado no navegador, no celular. Typecheck e suíte completa verdes.
