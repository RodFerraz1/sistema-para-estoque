# 02: Ruptura pela cobertura em dias, com o lead time fora do cálculo

**What to build:** o comprador chefe passa a ver a ruptura do jeito dele (ADR-0006). A cobertura aparece em dias em todas as telas e no chat. O painel tem o grupo "Em ruptura", com os SKUs cuja cobertura em dias está abaixo do piso de alerta, do que segura menos dias para o que segura mais e com disponível zero no topo. A política tem a opção de ignorar o lead time, que vira o padrão, e a sugestão de pedido sem lead time compra o que falta para cobrir o piso de reposição mais o ciclo de compra a partir da posição de hoje.

**Blocked by:** 01

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Ruptura e cobertura em dias")

- [ ] `LeadTimeBase` ganha `ignorar` e `LeadTimeOrigem` ganha `ignorado`. Com `ignorar`, o estoque na chegada é a posição e a memória de cálculo mostra lead time zero com origem `ignorado`. O critério `menor_lead_time` continua ordenando pelo lead time do fornecedor.
- [ ] Migration: a versão padrão passa a `lead_time_base = ignorar` e `motivos_de_alerta = (abaixo_do_piso_alerta)` (a entrega atrasada entra no ticket 09). Versões gravadas pelo comprador não mudam. O downgrade funciona.
- [ ] `inventory` expõe a cobertura em dias (uma conversão só). A API devolve `cobertura_meses` e `cobertura_dias` onde hoje devolve cobertura.
- [ ] O painel troca "Vão faltar antes da compra chegar" por "Em ruptura" (ordem: disponível zero, depois cobertura em dias crescente). `ruptura_antes_da_chegada` só aparece, em grupo próprio, quando estiver nos motivos da política.
- [ ] A tela do SKU, os cards do painel e a tela de política mostram dias. Na política, o piso de alerta aparece como "Quantos dias de venda o estoque precisa segurar?" e o lead time como pergunta com a opção "Não usar o prazo do fornecedor".
- [ ] Os textos dos alertas e o contexto do redator do chat falam em dias de cobertura. Os evals do chat continuam passando.
- [ ] Testes HTTP: SKU abaixo do piso em "Em ruptura", disponível zero primeiro, nenhum `ruptura_antes_da_chegada` com lead time ignorado, quantidade sugerida com `ignorar` batendo com um exemplo numérico, e uma política gravada com `observado` calculando como antes.
- [ ] Verificado no navegador. Typecheck e suíte completa verdes.
