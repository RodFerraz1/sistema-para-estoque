# O Copilot termina na decisão de compra, não em aprovação de pedido

Status: accepted (2026-10-01)

A fila de aprovação (M7) tratava o comprador chefe como aprovador. Ele recebia uma lista de sugestões, aprovava ou rejeitava cada uma, e aprovar criava o pedido de compra no ERP fake, com faixa de aprovação. O comprador real não trabalha assim. Ele descobre o problema por um aviso da equipe de vendas ou por um relatório do BI, olha o giro do SKU, negocia preço com o representante e lança o pedido no ERP real (Maos, sem integração).

Por isso o fluxo passa a ser este:

1. O **painel de alertas** é a home. Ele junta os avisos da equipe de vendas e os motivos de alerta do `purchasing`, calculados na hora.
2. A **tela do SKU** junta ficha, sugestão de pedido, sinais do corpus, avisos, histórico de preço, substitutos e o chat no contexto do SKU.
3. O fluxo termina numa **decisão de compra** (`vou_comprar`, `negociando`, `nao_comprar_agora`), que fecha os avisos e tira o SKU do painel por um prazo. O Copilot não cria pedido de compra.

Removemos a fila de aprovação, a faixa de aprovação e a criação de pedido no ERP fake (`purchasing.submeter_pedido`). Os motivos de destaque viram motivos de alerta.

## Considered Options

- **Manter a aprovação como ação dentro da tela do SKU**: rejeitada. Mantém o peso de "aprovar" que o comprador não reconheceu e cria pedidos num ERP que não é o real.
- **Decisão de compra e criação de pedido opcional**: rejeitada. São dois finais para o mesmo fluxo, e a faixa de aprovação continuaria só para servir um caminho que ninguém usa.

## Consequences

- O módulo `aprovacao` dá lugar a um módulo de decisões de compra e avisos. As tabelas da fila e as faixas saem por migration.
- O Copilot deixa de escrever pedidos no ERP fake. Para ele, o ERP volta a ser só leitura.
- A demo do M8 e o README descrevem a fila e precisam ser refeitos.
- Se um dia houver integração com o Maos, a criação de pedido volta como passo depois da decisão, não como aprovação.
