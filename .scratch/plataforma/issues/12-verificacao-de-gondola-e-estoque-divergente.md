# 12: Verificação de gôndola e estoque divergente

**What to build:** o repositor registra o que achou em cada SKU: `repus`, `estava_na_gondola` ou `sem_estoque_no_deposito`, com comentário opcional. O SKU sai da lista dele no dia e volta só se a venda continuar parada por mais um dia aberto inteiro. `sem_estoque_no_deposito` põe o SKU no painel do comprador como estoque divergente (o ERP diz que tem, o depósito diz que não). O repositor é notificado de SKU novo na lista, e o comprador de estoque divergente.

**Blocked by:** 10, 11

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seções "Repositor: queda de venda e verificação de gôndola" e "Episódios de alerta e notificações")

- [ ] Tabela `verificacoes_gondola` com o disponível do ERP no momento e o `usuario_id`. `POST` e `GET /skus/{sku_code}/verificacoes`.
- [ ] Regra de saída e volta do painel do repositor conforme a spec.
- [ ] `MotivoAlerta` ganha `estoque_divergente`, ligado na versão padrão por migration. O episódio fecha com uma decisão de compra no SKU ou quando o disponível do ERP muda.
- [ ] A varredura passa a abrir episódios `queda_de_venda` (para `reposicao`, exceto SKU verificado no dia) e `estoque_divergente` (para `comprador`).
- [ ] UI: os três botões e o comentário nos cards do repositor. Na tela do SKU do comprador, o bloco de verificações. No painel do comprador, o grupo ou o selo de estoque divergente.
- [ ] Testes HTTP: a verificação do dia tira o SKU, um dia aberto a mais parado traz de volta, `sem_estoque_no_deposito` gera estoque divergente, a decisão de compra fecha. Contrato do repositório em memória e no Postgres.
- [ ] Verificado no navegador. Typecheck e suíte completa verdes.
