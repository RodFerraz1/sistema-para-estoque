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
Hoje: 2 meses (pedido do dev para o MVP: "no mínimo 60 dias de cobertura de venda"). Quanto maior, maiores e mais raros os pedidos. [`ciclo_compra_meses`]
Resposta:

## Fornecedor

**6. Quando dois fornecedores vendem o mesmo produto, o que pesa mais: preço ou prazo de entrega?**
Hoje: preço (chute). [`criterio_fornecedor`]
Resposta:

**7. Para planejar, você confia no prazo que o fornecedor promete, no prazo que ele costuma cumprir de verdade, ou sempre no mais longo dos dois?**
Hoje: em nenhum dos dois. Na reunião de 2026-10-03 você disse que não confia no prazo, então o sistema ignora o prazo por padrão: avisa pela venda diária e compra contando de hoje (ADR-0006). Se um dia o prazo ficar confiável, dá para voltar ao que ele costuma cumprir. Exemplo: a Katrina promete 45 dias e tem entregado em 62. [`lead_time_base`]
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

## Plataforma: o que supusemos sem você (spec 09)

A reunião de 2026-10-03 trouxe o painel do repositor, a consulta da vendedora, as entregas atrasadas e os usuários. Algumas lacunas viraram suposições para o trabalho não parar. Cada uma está no sistema como um número ou uma regra fácil de trocar.

**15. Os dias que o estoque precisa segurar valem para todos os produtos, ou mudam por categoria ou por produto?**
Hoje: um número só para tudo, o mesmo da pergunta 3 (20 dias). Um número por categoria ou por produto é outra mudança, maior. [`piso_alerta_dias`]
Resposta:

**16. Agora a compra sugerida também não usa o prazo do fornecedor: ela cobre a folga da pergunta 4 mais o ciclo da pergunta 5, contando de hoje. Se a mercadoria demorar, a folga vai sendo consumida antes de chegar. A folga de 30 dias basta, ou você quer aumentar?**
Hoje: 30 dias. [`piso_reposicao_dias`]
Resposta:

**17. No Maos, o pedido de compra tem uma data prevista de entrega em que dá para confiar?**
Hoje: o sistema só chama de entrega atrasada o pedido com data prevista já vencida. Pedido sem data nunca fica atrasado. Sem essa data, a alternativa seria contar os dias desde o envio contra o prazo prometido, o que traz de volta o prazo em que você não confia.
Resposta:

**18. Quando você cobra o fornecedor por uma entrega atrasada, cobra o pedido inteiro ou produto por produto?**
Hoje: o pedido inteiro. A cobrança tira o pedido do painel até a nova previsão ou, sem previsão, por 7 dias.
Resposta:

**19. A loja abre em feriado? Tem dias em que ela abre e vende muito pouco?**
Hoje: o sistema não tem calendário. Dia em que a loja inteira não vendeu nada conta como loja fechada (domingo, por exemplo). Um feriado aberto com pouca venda pode parecer que um produto parou de vender.
Resposta:

**20. Quando um produto que vendia bem para de vender, quantos dias você espera antes de mandar o repositor olhar a gôndola? E a partir de quanto por dia um produto "vende bem"?**
Hoje: 2 dias abertos seguidos muito abaixo do normal, só para produtos que vendem ao menos 1 por dia, com uma chance de 1% de ser só azar. É um chute a partir do exemplo do tapete; a primeira semana de uso deve calibrar, e as vezes em que o repositor responde "estava na gôndola" mostram os alarmes falsos. [`dias_observados_queda`, `venda_diaria_minima_queda`, `limiar_queda`]
Resposta:

**21. Além de saber se tem estoque, se vem compra e quando chega, o que as vendedoras precisam ver? E que dados seus o Copilot ainda não mostra?**
Hoje: a vendedora vê o disponível, a previsão de chegada e o que aconteceu com os avisos dela. Você ganhou a tela de Estoque, as entregas atrasadas e o histórico de atraso de cada fornecedor.
Resposta:

**22. Os quatro papéis (comprador, vendas, reposição e administrador) bastam? Alguém precisa de um acesso diferente?**
Hoje: as permissões de cada papel são fixas. Uma pessoa pode ter mais de um papel.
Resposta:

**23. O celular das vendedoras é delas ou é compartilhado no balcão?**
Hoje: quem entra fica conectado por 30 dias, para não digitar a senha toda hora. Num celular compartilhado, cada uma precisa sair da conta ao terminar.
Resposta:

**24. Tudo bem a notificação aparecer só quando alguém está com o Copilot aberto?**
Hoje: não há nada rodando por trás. O Copilot confere os alertas quando alguém abre uma tela (e a cada 2 minutos com a tela aberta), então a hora da notificação pode ser depois da hora em que o produto entrou em ruptura. WhatsApp, e-mail e push ficam para depois.
Resposta:

**25. O Maos sabe em que setor da loja fica cada produto?**
Hoje: os setores são uma lista simples que o administrador cadastra no Copilot (Banho, Cama, Mesa, Cozinha, Tapetes), e o Copilot aprende o setor de cada produto pelos avisos de gôndola vazia e pelas verificações. Se o Maos tiver esse dado, ele substitui o que o Copilot aprendeu.
Resposta:

**26. A vendedora sempre sabe qual produto falta na gôndola, ou às vezes só vê o espaço vazio?**
Hoje: o aviso de gôndola vazia exige o produto, a cor e o tamanho. Um aviso só com o setor não existe; o comentário serve de escape.
Resposta:

**27. Para dividir a gôndola entre as cores, a venda dos últimos meses serve, mesmo contando os dias em que a cor faltou na loja?**
Hoje: a divisão usa a venda dos últimos 90 dias abertos, sem corrigir os dias em que faltou. Uma cor que ficou dias sem estoque ou com a gôndola vazia sai com uma parte menor do que a procura de verdade. [`dias_mix_gondola`]
Resposta:

**28. As cores e os tamanhos de um produto dividem a mesma gôndola, ou cada tamanho tem a sua?**
Hoje: o repositor informa quantas peças cabem por produto, e todas as cores e tamanhos dividem esse espaço.
Resposta:

**29. Um produto que quase não vende ainda deve ter ao menos uma peça na gôndola?**
Hoje: sim, toda cor e tamanho com estoque ganha ao menos uma peça, mesmo que venda pouco.
Resposta:
