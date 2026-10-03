# Ruptura pela cobertura em dias, com o lead time fora do cálculo padrão

Status: accepted (2026-10-03)

O alerta principal do painel era "ruptura antes da chegada": a posição comparada com o consumo durante o lead time do fornecedor. O comprador chefe não confia no lead time, porque ele muda com o frete, com o fornecedor e com crises no transporte. Para ele, um SKU está em **ruptura** quando a cobertura em dias (disponível dividido pela venda média diária) fica abaixo dos dias que o estoque precisa segurar, que é o piso de alerta da política.

Por isso:

1. `LeadTimeBase` ganha `ignorar`, que passa a ser o padrão. Com ele, o mecanismo usa lead time zero: o estoque na chegada é a posição de hoje. A sugestão de pedido e o alerta passam a usar a mesma conta.
2. O motivo de alerta padrão passa a ser `abaixo_do_piso_alerta`, que a UI chama de ruptura. `ruptura_antes_da_chegada` continua disponível para quem ligar o lead time de novo.
3. A cobertura aparece em dias para as pessoas. O domínio continua em meses, com uma conversão só.

É uma mudança de parâmetro e não de mecanismo, então a ADR-0003 continua valendo. Versões de política já gravadas não mudam.

## Considered Options

- **Manter o lead time e só mudar o alerta**: rejeitada. O alerta diria "está em ruptura" e a sugestão diria "não precisa comprar", porque continuaria descontando o lead time.
- **Tirar o lead time do mecanismo**: rejeitada. Quando houver lead time real por fornecedor (roadmap), ele deve voltar como opção da política, sem mudar o código.
- **Trocar a unidade de cobertura para dias no domínio inteiro**: rejeitada por enquanto. A política (teto, ciclo) é em meses e a troca mexeria em tudo sem mudar o comportamento. Só a apresentação muda.

## Consequences

- Sem lead time, a compra pode chegar depois que o piso de reposição já foi consumido. O piso de reposição vira a folga que absorve o prazo de entrega, e o comprador pode querer aumentá-lo.
- O alerta `periodo_sazonal` passa a olhar a partir de hoje, e não da data de chegada.
- Entrega atrasada vira o jeito de lidar com prazo: em vez de prever quando a compra chega, o Copilot mostra quando ela já devia ter chegado.
