# 02: Ruptura pela cobertura em dias, com o lead time fora do cálculo

**What to build:** o comprador chefe passa a ver a ruptura do jeito dele (ADR-0006). A cobertura aparece em dias em todas as telas e no chat. O painel tem o grupo "Em ruptura", com os SKUs cuja cobertura em dias está abaixo do piso de alerta, do que segura menos dias para o que segura mais e com disponível zero no topo. A política tem a opção de ignorar o lead time, que vira o padrão, e a sugestão de pedido sem lead time compra o que falta para cobrir o piso de reposição mais o ciclo de compra a partir da posição de hoje.

**Blocked by:** 01

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Ruptura e cobertura em dias")

- [x] `LeadTimeBase` ganha `ignorar` e `LeadTimeOrigem` ganha `ignorado`. Com `ignorar`, o estoque na chegada é a posição e a memória de cálculo mostra lead time zero com origem `ignorado`. O critério `menor_lead_time` continua ordenando pelo lead time do fornecedor.
- [x] Migration: a versão padrão passa a `lead_time_base = ignorar` e `motivos_de_alerta = (abaixo_do_piso_alerta)` (a entrega atrasada entra no ticket 09). Versões gravadas pelo comprador não mudam. O downgrade funciona.
- [x] `inventory` expõe a cobertura em dias (uma conversão só). A API devolve `cobertura_meses` e `cobertura_dias` onde hoje devolve cobertura.
- [x] O painel troca "Vão faltar antes da compra chegar" por "Em ruptura" (ordem: disponível zero, depois cobertura em dias crescente). `ruptura_antes_da_chegada` só aparece, em grupo próprio, quando estiver nos motivos da política.
- [x] A tela do SKU, os cards do painel e a tela de política mostram dias. Na política, o piso de alerta aparece como "Quantos dias de venda o estoque precisa segurar?" e o lead time como pergunta com a opção "Não usar o prazo do fornecedor".
- [x] Os textos dos alertas e o contexto do redator do chat falam em dias de cobertura. Os evals do chat continuam passando.
- [x] Testes HTTP: SKU abaixo do piso em "Em ruptura", disponível zero primeiro, nenhum `ruptura_antes_da_chegada` com lead time ignorado, quantidade sugerida com `ignorar` batendo com um exemplo numérico, e uma política gravada com `observado` calculando como antes.
- [x] Verificado no navegador. Typecheck e suíte completa verdes.

## Comments

**2026-10-03 (agente):** `LeadTimeBase.IGNORAR` (padrão em `PARAMETROS_V1`) e `LeadTimeOrigem.IGNORADO`: lead time zero, estoque na chegada igual à posição. Com `ignorar`, o critério de fornecedor ordena pelo lead time observado (ou o contratado, sem observado), que é o que a base `observado` já fazia. Migration `0013_lead_time_ignorado` aceita `ignorar` na constraint e troca só a v1 que ainda está no padrão antigo; o downgrade volta a v1 e, como a constraint antiga não conhece `ignorar`, passa outras versões com ele para `observado`. A conversão para dias é `inventory.schemas.dias_de_cobertura`: `Cobertura.dias`, `SKUAbaixoDoPiso.cobertura_dias` e `MemoriaCalculo.cobertura_na_chegada_dias` são campos calculados, e o item do painel ganha `cobertura_atual_dias` e `cobertura_na_chegada_sem_compra_dias`. Em `/skus/{sku}/analise` o campo novo fica dentro de `cobertura` (`meses`, `dias`), sem achatar o objeto. O painel continua uma lista só, agora ordenada por grupo (aviso, ruptura, ruptura antes da chegada, outros) e, em cada grupo, disponível zero, cobertura em dias crescente e código; a UI agrupa e busca a política para mostrar o piso e esconder os grupos cujo motivo está fora dela. Dias aparecem inteiros para baixo ("menos de 1 dia" abaixo de 1), na UI e no contexto do redator; o teto e o ciclo continuam em meses. Os testes antigos do `purchasing` rodam com uma v1 de lead time observado (`InMemoryPoliticaCompraRepositorio(v1=...)`), e o cenário do painel ganhou `ZERADO`. Para os próximos tickets: com o seed atual e o padrão novo, só `PM-AZUL-3040-02` fica em ruptura e quase nenhum SKU da Katrina pede compra; o smoke de sinais passou a usar `JDCP-BRAN-CASAL-01`. O ticket 05 (seed) deve criar os cenários de ruptura. `entrega_atrasada` não entrou nos motivos padrão (fica para o 09). Suíte com 804 testes verde; pyright com os mesmos 79 erros por arquivo.
