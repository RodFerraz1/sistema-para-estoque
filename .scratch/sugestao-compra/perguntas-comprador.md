# Perguntas para o comprador chefe

O Copilot sugere quanto comprar de cada produto. Para a sugestão ficar do jeito que você trabalha, ele precisa de algumas regras suas. Hoje o sistema está usando os valores da política de estoque escrita em agosto/2024 e, onde ela não diz nada, um chute nosso.

Responda do jeito que você faz na prática, não do jeito "certo". Se não souber, deixe em branco que o chute continua valendo.

Essas perguntas também são o rascunho da tela de onboarding (M7). Cada uma corresponde a um parâmetro da política de compra, indicado entre colchetes para o desenvolvedor.

## Estoque máximo

**1. Logo depois que uma compra chega, qual o máximo de meses de estoque que você aceita ter de um produto?**
Hoje: 3 meses (política de 2024, regra R1). [`teto_meses`]
Resposta:

**2. Em datas fortes, quantos meses a mais você aceita ter? E quais são essas datas para vocês?**
Hoje: até 2 meses a mais (R2), em maio (dia das mães), junho (namorados), novembro e dezembro (Natal). A política também cita volta às aulas, mas deixamos de fora. [`extra_sazonal_meses`, `meses_quentes`]
Resposta:

## Estoque mínimo

**3. Com quantos dias de estoque um produto deve acender o alerta de "está acabando"?**
Hoje: 20 dias (R4). [`piso_alerta_dias`]
Resposta:

**4. Quando uma compra chega, quantos dias de estoque você quer ainda ter como folga, antes de começar a vender a mercadoria nova?**
Hoje: 30 dias (R4). [`piso_reposicao_dias`]
Resposta:

## Ritmo de compra

**5. De quanto em quanto tempo você costuma comprar de novo o mesmo produto?**
Hoje: 1 mês (chute). Quanto maior, maiores e mais raros os pedidos. [`ciclo_compra_meses`]
Resposta:

## Fornecedor

**6. Quando dois fornecedores vendem o mesmo produto, o que pesa mais: preço ou prazo de entrega?**
Hoje: preço (chute). [`criterio_fornecedor`]
Resposta:

**7. Para planejar, você confia no prazo que o fornecedor promete, no prazo que ele costuma cumprir de verdade, ou sempre no mais longo dos dois?**
Hoje: no que ele costuma cumprir (chute). Exemplo: a Katrina promete 45 dias e tem entregado em 62. [`lead_time_base`]
Resposta:

## Épocas do ano

**8. Quando uma compra vai chegar numa data forte, você quer que o sistema avise, ou prefere que ignore?**
Hoje: avisa (chute). Ajustar a quantidade automaticamente pela época ainda não existe. [`sazonalidade_modo`]
Resposta:

## Produto novo

**9. Quantos dias de venda um produto novo precisa ter antes do sistema sugerir recompra sozinho?**
Hoje: 60 dias (R3). Antes disso, o sistema não sugere e a decisão fica com você. [`dias_historico_minimo`]
Resposta:

## Confirmar como o sistema entende os dados do ERP

Aqui não é preferência, é para confirmar se entendemos certo como vocês trabalham.

**10. O que é a quantidade "reservada" no estoque? Ela já está vendida e não pode contar como disponível?**
Hoje: o sistema usa só a quantidade disponível e ignora a reservada.
Resposta:

**11. Um pedido de compra aprovado, mas que ainda não foi enviado ao fornecedor, já conta como mercadoria a caminho?**
Hoje: sim. Rascunho não conta.
Resposta:

**12. O pedido mínimo por produto (MOQ) é uma quantidade mínima, ou tem que ser múltiplo de uma caixa fechada?**
Hoje: quantidade mínima, sem múltiplo.
Resposta:

**13. Um pedido que já está a caminho sempre chega antes de um pedido novo que eu faço hoje?**
Hoje: o sistema assume que sim.
Resposta:

**14. Para medir quanto um produto vende por mês, a média dos últimos 6 meses faz sentido para vocês?**
Hoje: sim, média dos 6 últimos meses fechados. Esta não é configurável por enquanto.
Resposta:
