---
Status: ready-for-agent
Escopo: tirar o Copilot do MVP e transformá-lo numa plataforma da operação de estoque do atacadista: ruptura pela cobertura em dias, notificação, busca e filtros em escala, entregas atrasadas, usuários com papéis, painel do repositor (queda de venda, aviso de gôndola vazia, verificação de gôndola e mix de gôndola) e consulta da vendedora
Vocabulário: ver /CONTEXT.md (termos novos desta spec: Ruptura, Cobertura em dias, Entrega atrasada, Cobrança de entrega, Episódio de alerta, Notificação, Usuário, Papel, Repositor, Gôndola, Queda de venda, Verificação de gôndola, Estoque divergente, Aviso de gôndola vazia, Setor, Mix de gôndola, Capacidade da gôndola, Participação nas vendas, Similar)
Decisões arquiteturais base: ADR-0001, ADR-0002, ADR-0003, ADR-0005, ADR-0006 (ruptura pela cobertura em dias, lead time fora do cálculo padrão), ADR-0007 (usuários, sessão e papéis)
Depende de: `.scratch/fluxo-comprador/` fechado (o ticket 07 estava `in-progress` e o trabalho dele não está commitado quando esta spec foi escrita)
Origem: reunião do dev com o comprador chefe, transcrita em `/whisperflow-feedbacks.md` (2026-10-03). Escrita com o dev AFK: as lacunas viraram suposições explícitas em "Further Notes", sem travar a spec
---

# Spec 09 - Plataforma: do Copilot de compras à operação de estoque

## Problem Statement

O comprador chefe usou o Copilot e gostou do rumo, mas o produto só cobre um pedaço do trabalho. Compra é uma cadeia que vai da necessidade do cliente da loja até a mercadoria estar na gôndola, e hoje o Copilot só olha para o comprador e, de leve, para a equipe de vendas. Os problemas que ele relatou:

1. **A ruptura está calculada do jeito errado.** O Copilot diz que um SKU vai faltar comparando a posição com o consumo durante o lead time do fornecedor. O comprador não confia no lead time: ele muda com o frete, com o fornecedor e com crises no transporte. Para ele, ruptura é simples: venda média diária, quantos dias o estoque precisa segurar e, quando o estoque cair abaixo disso, ele precisa ser avisado.
2. **Ninguém avisa o comprador.** O painel de alertas existe, mas o comprador só vê o problema se abrir o painel. Ele quer um pop-up ou uma notificação quando um SKU entra em ruptura.
3. **Não escala.** O ERP fake tem cerca de 80 SKUs. Uma loja de verdade tem milhares. Sem busca e sem filtros por código, categoria e nome, o painel e as listas viram uma parede de cards. E o painel calcula a sugestão de pedido de cada SKU a cada abertura, o que fica lento com milhares de SKUs.
4. **Entrega atrasada não aparece.** Quando um SKU zera e já existe pedido de compra para ele, o problema não é comprar, é cobrar o fornecedor. Hoje o Copilot não diferencia "precisa comprar" de "já comprei e não chegou".
5. **O produto parou de vender e ninguém percebeu.** O exemplo do comprador: um tapete marrom vende 10 por dia, no dia seguinte vende 5 e no outro vende 0, mas o sistema tem estoque. O que faltou foi a reposição da gôndola: a mercadoria está no depósito e não na loja. Quem resolve isso é o repositor, que não tem nenhuma tela no Copilot.
6. **Todo mundo é anônimo.** Vendedoras e comprador digitam o nome à mão. Não há como mostrar a cada pessoa só o que é dela, nem saber quem fez o quê.
7. **O repositor não sabe o que pôr na gôndola.** O atacadista compra 100 tapetes em 5 cores, 20 de cada, e o repositor expõe 5 de cada cor. Mas o marrom vende muito mais que o branco: falta marrom na gôndola e sobra branco. O repositor não sabe qual cor vende mais nem quanto de cada uma deveria expor.
8. **A vendedora vê pouco.** Ela consegue avisar que um SKU acabou, mas não consegue consultar se tem estoque, se vem compra nem quando chega, e não sabe o que aconteceu com o aviso que mandou. E quando ela passa por uma gôndola vazia, não tem como avisar o repositor: ela vê o problema antes de qualquer cálculo, mas o recado se perde no balcão.

## Solution

O Copilot vira uma plataforma com um painel por papel, alimentado pelos mesmos dados do ERP:

1. **Ruptura pela cobertura em dias (ADR-0006).** A política de compra ganha a opção de ignorar o lead time, que passa a ser o padrão. A cobertura aparece em dias para o comprador. Um SKU está em **ruptura** quando a cobertura em dias fica abaixo do piso de alerta ("quantos dias de venda o estoque precisa segurar"). A sugestão de pedido, com o lead time ignorado, compra o que falta para cobrir o piso de reposição mais o ciclo de compra a partir da posição de hoje.
2. **Notificações dentro do Copilot.** Quando um SKU entra em ruptura, quando uma entrega atrasa, quando chega aviso da equipe de vendas ou quando aparece uma queda de venda, nasce uma **notificação** para o papel certo. Ela aparece num sino no cabeçalho e, se for nova desde a última visita, num pop-up. Canais fora do Copilot (WhatsApp, e-mail, push) ficam no roadmap.
3. **Busca e filtros em escala.** O painel ganha busca por código, nome, cor e tamanho e filtro por categoria e por motivo. Uma tela nova de **Estoque** lista todos os SKUs, com paginação, os mesmos filtros e ordenação pela cobertura em dias. O painel passa a ler o ERP em lote, para abrir rápido com milhares de SKUs.
4. **Entregas atrasadas.** Um item de pedido de compra cuja data prevista de entrega já passou, com quantidade pendente, vira **entrega atrasada**, um motivo de alerta. O painel do comprador agrupa as entregas atrasadas por fornecedor, porque ele liga para o fornecedor e não para cada SKU. Ele registra uma **cobrança de entrega**, com nova previsão opcional, e o alerta some até essa data.
5. **Usuários e papéis (ADR-0007).** Login com e-mail e senha, sessão longa (a vendedora loga uma vez no celular) e quatro papéis: comprador, vendas, reposição e admin. O admin cadastra as pessoas. Avisos, decisões, cobranças e verificações passam a registrar o usuário logado. Cada papel cai na sua tela inicial.
6. **Painel do repositor.** O Copilot detecta **queda de venda**: um SKU que vende com regularidade e cuja venda dos últimos dias ficou muito abaixo do esperado. Com isso:
   - se há estoque disponível, a suspeita é a gôndola, e o SKU vai para o painel do repositor;
   - se não há estoque e existe pedido de compra atrasado, vira entrega atrasada no painel do comprador;
   - se não há estoque nem pedido de compra, vira ruptura no painel do comprador.

   O repositor registra uma **verificação de gôndola**: `repus`, `estava_na_gondola` ou `sem_estoque_no_deposito`. A última vira **estoque divergente** no painel do comprador, porque o ERP diz que tem e o depósito diz que não.
7. **Consulta da vendedora.** A página da equipe de vendas passa a mostrar, para cada SKU buscado, se tem estoque, se vem compra e a previsão de chegada. Ela ganha a lista "Meus avisos", com o que o comprador decidiu sobre cada um.
8. **Aviso de gôndola vazia.** A vendedora que vê uma gôndola vazia busca o SKU, escolhe o setor da loja e avisa o repositor em poucos toques. O aviso entra no topo do painel do repositor, com notificação, e é fechado pela verificação de gôndola. A vendedora acompanha o resultado em "Meus avisos". Os setores são uma lista simples cadastrada pelo admin, e o Copilot lembra o setor de cada SKU.
9. **Mix de gôndola.** Para cada produto, o repositor informa quantas peças cabem na gôndola, e o Copilot divide esse espaço entre as cores e tamanhos pela participação de cada SKU nas vendas: 10 marrons e 2 brancos, e não 5 de cada. A divisão respeita o que há no depósito e garante ao menos uma peça de cada SKU com estoque. A tela do SKU do comprador mostra a mesma participação nas vendas, para ele comprar a grade na proporção do que vende.

**Roadmap, fora desta spec:** similar pelo ERP real, sazonalidade e volatilidade com machine learning sobre 5 anos de vendas, lead time real por fornecedor, notificação fora do Copilot e integração com o Maos. Ver "Out of Scope" e `.scratch/plataforma/roadmap.md`.

## User Stories

### Comprador chefe: ruptura pela cobertura em dias

1. Como comprador chefe, quero que a ruptura seja calculada pela venda média diária e pelos dias que o estoque precisa segurar, porque o lead time do fornecedor não é confiável.
2. Como comprador chefe, quero ver a cobertura dos SKUs em dias ("segura 12 dias"), porque é assim que eu penso o estoque.
3. Como comprador chefe, quero configurar na política quantos dias de venda o estoque precisa segurar, para o alerta de ruptura seguir a minha regra.
4. Como comprador chefe, quero escolher na política se o lead time entra no cálculo, para poder voltar a usá-lo quando tivermos o lead time real de cada fornecedor.
5. Como comprador chefe, quero que, por padrão, o lead time fique fora do cálculo, porque é o que combinei com o time.
6. Como comprador chefe, quero que a sugestão de pedido, sem lead time, compre o que falta para cobrir o piso de reposição mais o ciclo de compra a partir da posição de hoje, para a quantidade sugerida bater com a minha conta.
7. Como comprador chefe, quero que a memória de cálculo diga claramente quando o lead time foi ignorado, para eu não achar que a conta está errada.
8. Como comprador chefe, quero ver no painel um grupo "Em ruptura" com os SKUs abaixo do piso de alerta, do que segura menos dias para o que segura mais, para atacar primeiro o que acaba antes.
9. Como comprador chefe, quero ver destacado o SKU com disponível zero, porque já está faltando na loja.
10. Como comprador chefe, quero que o alerta "vai faltar antes da compra chegar" só apareça quando eu ligar o lead time na política, porque sem lead time ele não faz sentido.
11. Como comprador chefe, quero que as versões de política que eu já gravei continuem valendo como estão, para a mudança de padrão não alterar uma regra que eu escolhi.

### Comprador chefe: notificações

12. Como comprador chefe, quero ser avisado por um pop-up quando abrir o Copilot e algum SKU tiver entrado em ruptura desde a minha última visita, para não depender de olhar o painel.
13. Como comprador chefe, quero receber o pop-up também com o Copilot aberto, sem recarregar a página, para saber na hora.
14. Como comprador chefe, quero ver um sino no cabeçalho com o número de notificações não lidas, para saber que tem coisa nova.
15. Como comprador chefe, quero abrir o sino e ver a lista de notificações (ruptura, entrega atrasada, aviso da equipe de vendas, estoque divergente), das mais recentes para as mais antigas, para revisar o que aconteceu.
16. Como comprador chefe, quero clicar numa notificação e cair na tela do SKU ou na entrega atrasada, para agir na hora.
17. Como comprador chefe, quero marcar tudo como lido, para limpar o sino depois de revisar.
18. Como comprador chefe, quero receber uma notificação só uma vez enquanto o SKU continuar em ruptura, para não ser bombardeado pelo mesmo problema.
19. Como comprador chefe, quero ser notificado de novo se o SKU sair da ruptura e voltar a entrar, porque é um problema novo.
20. Como comprador chefe, quero que o pop-up junte várias notificações num só ("5 SKUs entraram em ruptura"), para não abrir cinco janelas.
21. Como comprador chefe, quero que o pop-up não apareça para SKUs com decisão de compra vigente, porque já estou cuidando deles.

### Comprador chefe: busca, filtros e estoque

22. Como comprador chefe, quero buscar no painel pelo código do SKU, pelo nome do produto, pela cor e pelo tamanho, sem me preocupar com acento ou maiúscula, para achar um SKU entre milhares.
23. Como comprador chefe, quero que a busca filtre enquanto eu digito, para não ter que apertar enter.
24. Como comprador chefe, quero filtrar o painel por categoria, para olhar só cama, ou só mesa, num dia de visita de representante.
25. Como comprador chefe, quero filtrar o painel por motivo (ruptura, entrega atrasada, aviso, estoque divergente), para tratar um tipo de problema de cada vez.
26. Como comprador chefe, quero filtrar o painel por fornecedor, para preparar a conversa com um representante.
27. Como comprador chefe, quero ver quantos SKUs cada grupo do painel tem, mesmo com filtro, para ter noção do tamanho do problema.
28. Como comprador chefe, quero que os filtros fiquem na URL, para mandar o link filtrado para alguém ou voltar a ele depois.
29. Como comprador chefe, quero uma tela de Estoque com todos os SKUs ativos, para consultar qualquer SKU, mesmo os que não estão no painel.
30. Como comprador chefe, quero ver na tela de Estoque o código, produto, cor, tamanho, categoria, disponível, em trânsito, venda média diária e cobertura em dias de cada SKU, para ter a visão geral que hoje tiro do ERP.
31. Como comprador chefe, quero ordenar a tela de Estoque pela cobertura em dias, pela venda média diária e pelo nome, para achar os extremos.
32. Como comprador chefe, quero que a tela de Estoque seja paginada e continue rápida com milhares de SKUs.
33. Como comprador chefe, quero filtrar a tela de Estoque por "só em ruptura", "sem venda" e "com compra em trânsito", para responder perguntas rápidas.
34. Como comprador chefe, quero clicar num SKU da tela de Estoque e cair na tela do SKU.
35. Como comprador chefe, quero que o painel abra em poucos segundos mesmo com milhares de SKUs, para continuar sendo a minha tela inicial.

### Comprador chefe: entregas atrasadas

36. Como comprador chefe, quero ver no painel as entregas atrasadas, ou seja, os pedidos de compra com data prevista vencida e mercadoria por chegar, para cobrar o fornecedor.
37. Como comprador chefe, quero ver as entregas atrasadas agrupadas por fornecedor, com os pedidos e os SKUs de cada um, porque eu ligo para o fornecedor uma vez e cobro tudo.
38. Como comprador chefe, quero ver quantos dias cada entrega está atrasada e quanto falta chegar, para saber o tamanho do atraso.
39. Como comprador chefe, quero ver primeiro as entregas atrasadas de SKUs em ruptura, porque é ali que estou perdendo venda.
40. Como comprador chefe, quero registrar que cobrei o fornecedor, com uma nova previsão de entrega opcional e um comentário, para guardar o que ele me disse.
41. Como comprador chefe, quero que a entrega cobrada saia do painel até a nova previsão (ou por 7 dias, se não houver nova previsão), para o painel mostrar só o que está pendente.
42. Como comprador chefe, quero que a entrega volte ao painel se a nova previsão passar sem a mercadoria chegar, para cobrar de novo.
43. Como comprador chefe, quero ver na tela do SKU as entregas pendentes dele, com a previsão original, as cobranças e a nova previsão, para responder à vendedora quando ela perguntar.
44. Como comprador chefe, quero que a entrega atrasada seja um motivo de alerta que eu posso ligar ou desligar na política, como os outros.
45. Como comprador chefe, quero ver o histórico de atrasos de um fornecedor (quantas entregas atrasaram e em média quantos dias), para usar na negociação.

### Comprador chefe: estoque divergente

46. Como comprador chefe, quero ver no painel os SKUs em que o repositor disse que não há estoque no depósito mas o ERP diz que há, para mandar fazer a contagem ou comprar.
47. Como comprador chefe, quero ver quem verificou, quando e qual era o disponível no ERP na hora, para conversar com a pessoa certa.
48. Como comprador chefe, quero registrar uma decisão de compra sobre um SKU com estoque divergente, como faço com os outros alertas, para tirá-lo do painel.

### Usuários e papéis

49. Como admin, quero cadastrar uma pessoa com nome, e-mail, senha inicial e papéis, para ela usar o Copilot.
50. Como admin, quero dar mais de um papel à mesma pessoa, porque numa loja pequena o repositor às vezes também vende.
51. Como admin, quero desativar uma pessoa que saiu da empresa, sem apagar o que ela registrou, para ela não entrar mais e o histórico continuar.
52. Como admin, quero redefinir a senha de uma pessoa que esqueceu, para ela voltar a entrar sem depender de e-mail.
53. Como admin, quero ver a lista de pessoas com papéis, situação e último acesso, para saber quem usa o Copilot.
54. Como pessoa cadastrada, quero entrar com e-mail e senha, para usar o Copilot.
55. Como vendedora, quero continuar logada no celular por semanas, para não digitar a senha a cada aviso.
56. Como pessoa cadastrada, quero sair da conta, para usar um celular ou computador compartilhado.
57. Como pessoa cadastrada, quero trocar a minha senha.
58. Como pessoa cadastrada, quero cair, depois de entrar, na tela inicial do meu papel (painel do comprador, aviso da equipe de vendas ou painel do repositor), para não procurar.
59. Como pessoa com mais de um papel, quero alternar entre as telas dos meus papéis pelo menu.
60. Como vendedora, quero que o aviso registre meu nome sozinho, para não digitar.
61. Como comprador chefe, quero que a decisão de compra registre meu nome sozinho.
62. Como comprador chefe, quero que só quem tem papel de comprador veja o painel do comprador, a política de compra, os preços pagos e o chat, porque são informações de negociação.
63. Como dev, quero que toda rota da API exija login, exceto o login e o health, para os dados do atacadista não ficarem abertos.
64. Como dev, quero que uma rota chamada por um papel sem permissão responda 403 e sem login responda 401, e que a UI leve ao login quando a sessão expirar.
65. Como dev, quero que o primeiro admin seja criado por um comando, para não existir senha padrão no código.
66. Como dev, quero que avisos e decisões gravados antes dos usuários continuem aparecendo com o nome que foi digitado na época.
67. Como dev, quero senhas guardadas com hash forte e várias tentativas de login erradas seguidas bloqueadas por alguns minutos, porque a página vai rodar no celular das vendedoras.

### Repositor: queda de venda e gôndola

68. Como repositor, quero abrir o Copilot no celular e ver os SKUs que provavelmente estão faltando na gôndola, para repor antes que a venda se perca.
69. Como repositor, quero ver em cada SKU o produto, a cor, o tamanho, quanto vendia por dia, quanto vendeu nos últimos dias e o disponível no ERP, para entender por que o SKU está ali.
70. Como repositor, quero ver primeiro os SKUs que mais vendiam, porque são os que mais perdem venda parados no depósito.
71. Como repositor, quero registrar que repus, para o SKU sair da minha lista.
72. Como repositor, quero registrar que o SKU estava na gôndola, para o sistema aprender que foi alarme falso e o SKU sair da lista.
73. Como repositor, quero registrar que não achei o SKU no depósito, para o comprador saber que o estoque do ERP está errado.
74. Como repositor, quero escrever um comentário opcional na verificação ("estava no lugar errado").
75. Como repositor, quero ser notificado quando um SKU novo entrar na minha lista, para não depender de abrir a tela.
76. Como repositor, quero que um SKU que verifiquei não volte para a lista no mesmo dia, a não ser que a venda continue parada por mais um dia inteiro, para não verificar a mesma coisa duas vezes.
77. Como repositor, quero buscar e filtrar a minha lista por categoria e nome, para organizar a ronda por corredor.
78. Como comprador chefe, quero que um SKU com queda de venda e sem estoque apareça como ruptura no meu painel, e não no do repositor, porque a solução é comprar.
79. Como comprador chefe, quero que um SKU com queda de venda, sem estoque e com pedido atrasado apareça como entrega atrasada, porque a solução é cobrar o fornecedor.
80. Como comprador chefe, quero ver na tela do SKU as verificações de gôndola dele, para entender quedas de venda que não foram falta de compra.
81. Como comprador chefe, quero ajustar na política a sensibilidade da detecção de queda de venda, para calibrar com a realidade da loja depois de usar.
82. Como repositor, quero que dias em que a loja não abriu (domingo, feriado) não contem como dia sem venda, para não receber alarme falso toda segunda-feira.
83. Como repositor, quero que SKUs que vendem pouco (uma peça por semana) não entrem na lista por um dia sem venda, porque isso é normal para eles.

### Equipe de vendas: consulta e acompanhamento

84. Como vendedora, quero buscar um SKU e ver se tem estoque, quantas unidades e, se não tem, se vem compra e quando chega, para responder ao cliente no balcão.
85. Como vendedora, quero ver a previsão de chegada como uma data simples ("chega por volta de 15/10") e "atrasada" quando a previsão já passou, para não prometer o que não sei.
86. Como vendedora, quero ver a lista "Meus avisos", com o que o comprador decidiu sobre cada um (vou comprar, negociando, não comprar agora com o motivo), para saber o que dizer ao cliente.
87. Como vendedora, quero ver a quantidade que o comprador disse que vai comprar, quando a decisão for `vou_comprar`.
88. Como vendedora, quero ser notificada quando o comprador decidir sobre um aviso meu, para não ficar perguntando.
89. Como vendedora, quero que a página continue simples no celular, com a busca no topo e alvos de toque grandes, mesmo com a consulta nova.
90. Como vendedora, não quero ver preço de compra, fornecedor, política nem o painel do comprador, porque não é da minha conta e atrapalha.

### Equipe de vendas e repositor: aviso de gôndola vazia

91. Como vendedora, quero avisar o repositor que a gôndola de um SKU está vazia, em poucos toques no celular, para a mercadoria voltar à loja antes de o cliente desistir.
92. Como vendedora, quero informar o setor da loja onde fica a gôndola vazia, para o repositor ir direto ao lugar.
93. Como vendedora, quero que o setor já venha preenchido quando o Copilot souber onde o SKU fica, para só confirmar.
94. Como vendedora, quero escrever um comentário opcional ("só sobrou o tamanho P"), para dar contexto ao repositor.
95. Como vendedora, quero ver em "Meus avisos" o que o repositor achou (repôs, estava na gôndola, não tinha no depósito), para saber o que dizer ao cliente.
96. Como vendedora, quero ser notificada quando o repositor verificar a gôndola que avisei.
97. Como vendedora, quero ser avisada, antes de enviar, quando o ERP diz que o SKU está sem estoque, e mesmo assim poder enviar, para não mandar o repositor procurar algo que não existe sem saber.
98. Como repositor, quero ver os avisos de gôndola vazia no topo do meu painel, antes da queda de venda, porque uma pessoa já viu o problema.
99. Como repositor, quero ver em cada aviso o SKU, o setor, quem avisou, quando e o disponível no ERP.
100. Como repositor, quero ser notificado na hora quando chegar um aviso de gôndola vazia.
101. Como repositor, quero filtrar o meu painel por setor, para fazer a ronda corredor por corredor.
102. Como repositor, quero que a minha verificação de gôndola feche o aviso, com os mesmos três resultados da queda de venda, para não registrar duas vezes.
103. Como repositor, quero que um SKU com aviso de gôndola vazia e queda de venda apareça uma vez só no meu painel, com os dois motivos, para não verificar duas vezes.
104. Como repositor, quero corrigir o setor de um SKU na verificação, quando a vendedora informar errado, para o próximo aviso já vir certo.
105. Como comprador chefe, quero que `sem_estoque_no_deposito` num aviso de gôndola vazia também vire estoque divergente no meu painel, quando o ERP disser que há estoque.
106. Como admin, quero cadastrar, renomear e desativar os setores da loja, para a lista bater com o layout real.

### Repositor: mix de gôndola

107. Como repositor, quero ver quantas peças de cada cor e tamanho de um produto colocar na gôndola, conforme o que mais vende, para não faltar marrom e sobrar branco.
108. Como repositor, quero informar quantas peças do produto cabem na gôndola e ver na hora a divisão entre as cores e tamanhos.
109. Como repositor, quero que o Copilot lembre a capacidade da gôndola de cada produto, para só ajustar quando o espaço mudar.
110. Como repositor, quero ver ao lado de cada SKU a participação dele nas vendas do produto e a venda média diária, para entender a divisão.
111. Como repositor, quero que a sugestão nunca passe do que há no depósito e que o espaço que sobra vá para o próximo SKU que mais vende, para conseguir cumprir a sugestão.
112. Como repositor, quero que cada SKU com estoque ganhe ao menos uma peça quando couber, para todas as cores continuarem expostas e terem a chance de vender.
113. Como repositor, quero abrir o mix do produto a partir do card de um SKU no meu painel, para repor a gôndola inteira de uma vez.
114. Como repositor, quero buscar um produto pelo nome e montar a gôndola dele mesmo sem alerta, para organizar a loja na ronda.
115. Como repositor, quero ver a participação nas vendas mesmo sem informar a capacidade, para ter a ordem de importância das cores.
116. Como comprador chefe, quero ver na tela do SKU a participação dele nas vendas do produto, para comprar a grade na proporção do que vende e não 20 de cada cor.

### Dev e operação

117. Como dev, quero um seed que gere vendas diárias realistas até a data em que o seed roda, para a detecção de queda de venda ter o que analisar e a giro não cair por falta de dado no mês corrente.
118. Como dev, quero cenários fixos no seed (o tapete marrom com queda de venda e estoque, um SKU em ruptura, um pedido atrasado, um SKU com queda de venda e sem estoque), para a demo e os smoke tests contarem a história do comprador.
119. Como dev, quero um modo do seed com milhares de SKUs, para medir o painel e a tela de Estoque em escala.
120. Como dev, quero que o painel, a tela de Estoque, o painel do repositor e a varredura de notificações façam um número fixo de consultas ao banco, independente do número de SKUs.
121. Como dev, quero smoke tests contra o Postgres para login, ruptura, entrega atrasada, queda de venda, verificação e notificação.
122. Como dev, quero que o README e o roteiro de demo contem a história nova: do tapete marrom que parou de vender até o comprador cobrando o fornecedor.
123. Como dev, quero que o chat do Copilot continue funcionando para o comprador, com as respostas usando cobertura em dias.

## Implementation Decisions

### Pré-requisito

- O trabalho de `.scratch/fluxo-comprador/` (ticket 07 ainda `in-progress` e um working tree grande sem commit) precisa ser fechado e commitado antes do primeiro ticket desta spec. Esta spec parte do painel, dos avisos, das decisões de compra e do chat lateral já existentes.

### Ruptura e cobertura em dias (ADR-0006)

- `LeadTimeBase` ganha o valor `ignorar`, que passa a ser o padrão da política. Com `ignorar`, o mecanismo usa lead time zero: estoque na chegada igual à posição e quantidade necessária igual a `giro * (piso_reposicao + ciclo) - posição` quando a posição fica abaixo do piso de reposição. É uma mudança de parâmetro, não de mecanismo, então cabe na ADR-0003. A ADR-0006 registra a mudança de padrão e o motivo.
- `LeadTimeOrigem` ganha `ignorado`. A memória de cálculo mostra lead time zero com essa origem. O critério de fornecedor `menor_lead_time` continua ordenando pelo lead time do fornecedor, mesmo quando o cálculo o ignora.
- **Cobertura em dias** = disponível / venda média diária, com venda média diária = giro / 30. É só outra unidade do mesmo conceito de cobertura. O domínio continua guardando meses e a conversão fica num lugar só (`inventory`). A API passa a devolver os dois campos (`cobertura_meses` e `cobertura_dias`), e a UI do comprador, da vendedora e do repositor mostra dias. O glossário troca o "_Avoid_: dias de estoque" da Cobertura por uma nota de que a cobertura aparece em dias para as pessoas.
- **Ruptura** é o nome, para o comprador, do motivo de alerta `abaixo_do_piso_alerta`: cobertura em dias abaixo do piso de alerta. O identificador no código não muda, para não exigir migration de dados. Só os textos mudam. O piso de alerta aparece na política como "Quantos dias de venda o estoque precisa segurar?".
- A migration da política troca o padrão (só a versão padrão, como na spec 08): `lead_time_base = ignorar` e `motivos_de_alerta = (abaixo_do_piso_alerta, entrega_atrasada)`. Versões gravadas pelo comprador não mudam.
- O grupo "Vão faltar antes da compra chegar" do painel vira "Em ruptura", ordenado pela cobertura em dias crescente, com disponível zero no topo. `ruptura_antes_da_chegada` continua existindo e entra num grupo próprio só quando estiver nos motivos da política.
- O alerta `periodo_sazonal` continua como está. A sazonalidade não muda nesta spec.
- O texto dos alertas, a sugestão no chat e o contexto montado para o redator passam a usar dias onde hoje dizem meses de cobertura.

### Escala: leitura em lote e filtros

- O painel hoje faz várias consultas por SKU (ficha, estoque, vendas, fornecedores, em trânsito). A porta do ERP ganha leituras em lote, um retrato do estoque inteiro:
  - `estoques()` com o disponível de todos os SKUs ativos;
  - `giros(desde)` com a soma de vendas por SKU e mês numa consulta agregada;
  - `vendas_diarias(desde)` com a soma por SKU e dia;
  - `fornecedores_por_sku()`;
  - `itens_em_transito()` de todos os SKUs.
- `purchasing` ganha `sugerir_pedidos(retrato)`, que calcula as sugestões de todos os SKUs a partir de um retrato já carregado. `sugerir_pedido(sku)` continua para a tela do SKU e passa a montar um retrato de um SKU só, para os dois caminhos usarem a mesma conta.
- Meta: com 5.000 SKUs ativos e 24 meses de vendas no Postgres local, `GET /painel` responde em menos de 2 segundos, com um número fixo de consultas, verificado por um teste que conta as consultas.
- Filtros do painel no servidor: `GET /painel?busca=&categoria=&motivo=&fornecedor=`. A busca usa a regra do `catalog.buscar_skus` atual (todas as palavras, sem acento nem maiúscula, em código, produto, cor e tamanho). As contagens por grupo vêm junto.
- Tela de **Estoque**: `GET /estoque?busca=&categoria=&situacao=&ordem=&pagina=&por_pagina=`, com `situacao` em `em_ruptura | sem_venda | com_transito`, `ordem` em `cobertura | venda_diaria | nome` e `por_pagina` de no máximo 100. Devolve itens e total. `GET /categorias` devolve as categorias com SKU ativo.
- A busca do painel e do Estoque roda na UI com debounce, e os filtros ficam na query string da página.

### Entregas atrasadas e cobrança

- `inventory` ganha `entregas_atrasadas(agora)`: itens de pedido de compra em `aprovado`, `enviado` ou `recebido_parcial`, com quantidade pendente e `data_prevista_entrega` anterior a hoje. Cada uma traz o pedido, o fornecedor, o SKU, a quantidade pendente, a data prevista e os dias de atraso. Pedido sem data prevista nunca está atrasado. Isso é uma suposição: ver "Further Notes".
- `MotivoAlerta` (e `TipoAlerta`) ganha `entrega_atrasada`. Um SKU tem esse motivo quando tem ao menos uma entrega atrasada sem cobrança vigente.
- A **cobrança de entrega** é dona do módulo `painel`, no schema `copilot`. Tabela `cobrancas_entrega`: id, pedido_id, fornecedor_id, nova_previsao (opcional), comentario (opcional), usuario_id, criado_em. Uma cobrança vale para o pedido inteiro, porque o comprador cobra o pedido e não o SKU. A cobrança vigente é a mais recente do pedido. Ela tira o pedido do painel até `nova_previsao` ou, sem nova previsão, por `PRAZO_DA_COBRANCA` = 7 dias (constante nomeada, como `PRAZO_DA_DECISAO`).
- `GET /painel` ganha a seção `entregas_atrasadas`: os fornecedores com pedidos atrasados sem cobrança vigente, cada um com os pedidos e os SKUs. Ordem: primeiro os fornecedores com algum SKU em ruptura, depois pelo maior atraso.
- Rotas: `POST /pedidos/{pedido_id}/cobrancas` e `GET /fornecedores/{id}/atrasos`, com o histórico de entregas recebidas atrasadas (`recebido_em` contra `data_prevista_entrega`), a quantidade e a média de dias.
- O ERP continua só leitura (ADR-0005). A nova previsão vive no Copilot, não no pedido.

### Episódios de alerta e notificações

- **Episódio de alerta**: o intervalo em que uma condição vale para um SKU (ou para um pedido, no caso de entrega atrasada). Tabela `episodios_alerta`: id, tipo (`ruptura | entrega_atrasada | aviso | queda_de_venda | estoque_divergente | decisao_sobre_aviso | gondola_vazia | verificacao_sobre_aviso`), sku_code (opcional), pedido_id (opcional), papel_destino, aberto_em, fechado_em (opcional), detalhe (json com os números do momento). Índice único parcial para não haver dois episódios abertos da mesma condição.
- Uma **varredura** compara as condições atuais com os episódios abertos: abre os novos e fecha os que deixaram de valer. Ela é idempotente e roda dentro de `GET /notificacoes`, com um lock consultivo do Postgres para duas varreduras simultâneas não duplicarem episódios. Não há job em segundo plano nesta spec: sem ninguém com o Copilot aberto, ninguém veria a notificação. O agendador fica no roadmap, junto dos canais externos.
- Os avisos da equipe de vendas e as decisões sobre avisos viram episódios na hora em que são registrados, sem esperar a varredura.
- Ruptura e queda de venda não abrem episódio para um SKU com decisão de compra vigente (ruptura) ou com verificação de gôndola do dia (queda de venda).
- **Notificação** é a visão de um episódio para um usuário. O usuário tem um cursor `notificacoes_vistas_ate`. Não lidas são os episódios do papel dele abertos depois do cursor. Por isso as notificações vêm depois dos usuários.
- Rotas: `GET /notificacoes` (roda a varredura e devolve as dos papéis do usuário, com o número de não lidas) e `POST /notificacoes/vistas`.
- UI: sino no cabeçalho de todas as telas logadas. Ao abrir uma tela e a cada 2 minutos com a aba visível, a UI chama `/notificacoes`. Se houver não lidas novas desde a última chamada, mostra um pop-up que agrupa por tipo ("5 SKUs entraram em ruptura") com link para a lista. O pop-up fecha sozinho e não bloqueia a tela.

### Usuários, sessão e papéis (ADR-0007)

- Módulo novo `usuarios`, no padrão dos módulos atuais (schemas, service, repositório como Protocol, versão em memória, versão Postgres, dependências do FastAPI).
- Tabela `usuarios`: id, nome, email (único, minúsculo), senha_hash, papeis (array de `comprador | vendas | reposicao | admin`), ativo, criado_em, ultimo_acesso_em, notificacoes_vistas_ate. Tabela `sessoes`: token_hash, usuario_id, criada_em, expira_em, revogada_em. Tabela `tentativas_login`, para o bloqueio.
- A senha usa argon2id, por uma biblioteca mantida. A sessão é um token aleatório num cookie `HttpOnly`, `SameSite=Lax` e `Secure` fora do ambiente local. Só o hash do token fica no banco. A sessão expira 30 dias depois do último uso e é renovada a cada uso. Sair revoga a sessão. Desativar o usuário revoga todas as sessões dele.
- Mudanças de estado (POST, PUT, DELETE) exigem o cabeçalho `X-Requested-With`, que a função `api()` da UI já pode mandar, como defesa simples contra CSRF junto com o `SameSite`.
- Bloqueio: 5 tentativas erradas para o mesmo e-mail em 15 minutos bloqueiam esse e-mail por 15 minutos.
- Dependências do FastAPI: `usuario_atual` (401 sem sessão) e `exige_papel(*papeis)` (403). Mapa de permissões:
  - `comprador`: painel, política, chat, tela do SKU completa, preços, decisões, cobranças e Estoque;
  - `vendas`: busca e consulta de SKU (sem preço de compra nem fornecedor), avisos ao comprador, avisos de gôndola vazia e "Meus avisos";
  - `reposicao`: painel do repositor, verificações, busca e consulta de SKU;
  - `admin`: gestão de usuários e de setores.
- Livres de login: `/health`, `/login` e os arquivos estáticos da tela de login. As outras páginas estáticas carregam e, no primeiro 401, mandam a pessoa para `login.html?volta=<página>`.
- Comando `python -m scripts.criar_admin` cria o primeiro admin, pedindo a senha no terminal.
- `avisos`, `decisoes_compra`, `cobrancas_entrega` e `verificacoes_gondola` ganham `usuario_id` (opcional para as linhas antigas). `avisado_por` e `decidido_por` continuam como texto gravado, preenchido pelo nome do usuário logado, para o histórico antigo não mudar. As rotas deixam de aceitar o nome no corpo.
- `registros_decisao` (chat) ganha `usuario_id`.
- Os testes HTTP trocam a dependência `usuario_atual` por um usuário fake com os papéis do cenário. Um teste à parte cobre login, sessão, expiração, bloqueio e 401/403 de verdade.
- Telas novas: `login.html`, `usuarios.html` (admin) e `conta.html` (trocar senha e sair). O cabeçalho mostra só os links dos papéis do usuário.

### Repositor: queda de venda e verificação de gôndola

- **Queda de venda** é código, sem Jev (ADR-0002: o Jev não faz conta). Para cada SKU ativo:
  - Venda diária base λ = média de unidades por dia aberto nos 28 dias abertos anteriores à janela observada.
  - Janela observada = os últimos `dias_observados_queda` dias abertos e fechados (padrão 2). Hoje, por não estar fechado, não entra.
  - **Dia aberto** = dia em que a loja inteira vendeu ao menos uma peça. Assim domingos e feriados saem sem precisar de calendário. É uma suposição: ver "Further Notes".
  - O SKU tem queda de venda quando λ ≥ `venda_diaria_minima_queda` (padrão 1 unidade por dia, para não pegar SKU de venda esporádica) e a probabilidade de vender no máximo o observado, numa Poisson de média λ vezes os dias da janela, fica abaixo de `limiar_queda` (padrão 0,01). No exemplo do tapete marrom, com λ = 10 e 5 + 0 vendidos em 2 dias, a probabilidade é da ordem de 10⁻⁵ e o SKU entra. Um SKU com λ = 0,3 que vendeu 0 em 2 dias tem probabilidade 0,55 e não entra.
  - `dias_observados_queda`, `venda_diaria_minima_queda` e `limiar_queda` são parâmetros novos da política de compra, com migration e padrão, marcados "a validar com o comprador" (ADR-0003).
- Destino da queda de venda, nesta ordem:
  1. disponível > 0: vai para o **painel do repositor**;
  2. disponível = 0 e o SKU tem entrega atrasada: entra no painel do comprador como entrega atrasada (o motivo `entrega_atrasada` já cobre isso), com o selo "parou de vender";
  3. disponível = 0 sem entrega atrasada: entra como ruptura, que já vale porque a cobertura é zero, com o selo "parou de vender".
- Módulo novo `reposicao` (dono da detecção e das verificações), que lê `sales`, `inventory` e `catalog` e o retrato em lote do ERP.
- Tabela `verificacoes_gondola`: id, sku_code, resultado (`repus | estava_na_gondola | sem_estoque_no_deposito`), comentario (opcional), disponivel_no_erp (número no momento), usuario_id, criado_em.
- Um SKU com verificação no dia de hoje sai do painel do repositor. Ele volta se, depois da verificação, um dia aberto inteiro fechar e a janela observada continuar com queda.
- `sem_estoque_no_deposito` abre um episódio `estoque_divergente` para o comprador e põe o SKU no painel do comprador com o motivo novo `estoque_divergente` (em `MotivoAlerta`, padrão ligado). O episódio fecha quando o comprador registra uma decisão de compra no SKU ou quando o disponível do ERP muda, o que indica que alguém ajustou o estoque.
- Rotas: `GET /reposicao/painel?busca=&categoria=`, `POST /skus/{sku_code}/verificacoes` e `GET /skus/{sku_code}/verificacoes`.
- Ordem do painel do repositor: maior venda perdida estimada primeiro, que é λ vezes os dias da janela menos o vendido.
- UI: `reposicao.html`, mobile first como `aviso.html`, com cards grandes, os três botões de resultado e o comentário opcional.

### Consulta e acompanhamento da vendedora

- `GET /skus/{sku_code}/disponibilidade` (papéis `vendas`, `reposicao` e `comprador`): disponível, uma frase de situação (`tem | pouco | acabou`, com "pouco" = em ruptura) e as entregas pendentes, cada uma com quantidade, previsão (a nova previsão da cobrança quando houver, se não a do pedido) e `atrasada`. Sem preço de compra nem fornecedor.
- `GET /avisos/meus`: os avisos do usuário logado nos últimos 30 dias, cada um com a decisão de compra que o fechou (tipo, quantidade quando for `vou_comprar`, motivo quando for `nao_comprar_agora` e data) ou "aguardando o comprador".
- Uma decisão de compra que fecha avisos abre episódios `decisao_sobre_aviso` para a vendedora de cada aviso. Ela e a verificação sobre aviso de gôndola são as únicas notificações dirigidas a uma pessoa, e não a um papel: o episódio guarda o usuario_id destino.
- `aviso.html` vira a tela da equipe de vendas, com três partes: busca com o resultado mostrando a disponibilidade, os botões "avisar o comprador" (o fluxo de aviso atual, sem o campo de nome) e "gôndola vazia", e "Meus avisos".

### Aviso de gôndola vazia e setores

- **Aviso de gôndola vazia** é um conceito separado do aviso ao comprador: tem outro destino (o repositor) e fecha de outro jeito (verificação de gôndola, não decisão de compra). Misturar os dois na mesma tabela quebraria a regra de aviso aberto do módulo `painel`. Fica no módulo `reposicao`.
- Tabela `setores`: id, nome (único), ativo. Gerida pelo admin (`GET/POST/PUT /setores`). O seed cria setores de exemplo (Banho, Cama, Mesa, Cozinha, Tapetes).
- Tabela `setores_sku`: sku_code, setor_id, atualizado_em, usuario_id. É o setor conhecido de cada SKU, gravado pelo último aviso de gôndola vazia ou pela verificação que corrigiu o setor. O ERP não tem essa informação.
- Tabela `avisos_gondola`: id, sku_code, setor_id, comentario (opcional), disponivel_no_erp (no momento), usuario_id, criado_em.
- **Aviso de gôndola aberto** é derivado, como o aviso ao comprador: está aberto se não existe verificação de gôndola do mesmo SKU registrada depois dele.
- Rotas: `POST /avisos-gondola` (papel `vendas`; SKU inexistente 404, inativo 422, setor inativo 422), `GET /skus/{sku_code}/setor`. `POST /skus/{sku_code}/verificacoes` aceita `setor_id` opcional, que corrige o setor do SKU.
- Painel do repositor: grupo "Avisos das vendedoras" no topo, ordenado pelo aviso mais antigo primeiro, e depois o grupo de queda de venda. Um SKU com aviso aberto e queda de venda aparece uma vez, no primeiro grupo, com os dois selos. `GET /reposicao/painel` ganha o filtro `setor`. O setor de um SKU sem aviso vem de `setores_sku` (pode ser vazio).
- Notificações: o aviso abre na hora um episódio `gondola_vazia` para o papel `reposicao`. A verificação que fecha avisos de gôndola abre episódios `verificacao_sobre_aviso` dirigidos à vendedora de cada aviso.
- `sem_estoque_no_deposito` num SKU com disponível no ERP maior que zero vira estoque divergente, com ou sem aviso de gôndola. Com disponível zero, o ERP e o depósito concordam e o SKU já está em ruptura no painel do comprador.
- `GET /avisos/meus` passa a juntar os dois tipos de aviso da vendedora, cada um com o seu desfecho (decisão de compra ou verificação de gôndola).
- Na UI da vendedora, o botão "gôndola vazia" abre um passo com o setor (lista dos setores ativos, pré-selecionado com o setor conhecido do SKU) e o comentário. Se o disponível no ERP for zero, a tela avisa antes de enviar, mas não impede o envio.

### Mix de gôndola

- **Participação nas vendas** de um SKU = a venda dele dividida pela venda de todos os SKUs ativos do mesmo produto, nos últimos `dias_mix_gondola` dias abertos (padrão 90, parâmetro novo da política). O grupo é o produto do catálogo (`produto_id`), com todas as cores e tamanhos.
- **Capacidade da gôndola**: peças do produto que cabem na gôndola, informadas pelo repositor. Tabela `capacidades_gondola`: produto_id, capacidade (> 0), usuario_id, atualizado_em. Vale a última.
- **Mix de gôndola**, calculado em código no módulo `reposicao`, com capacidade C e os SKUs ativos do produto:
  1. Elegíveis são os SKUs com disponível > 0.
  2. Se C ≥ número de elegíveis, cada elegível recebe 1 peça. Se não, as C peças vão, uma a cada, para os elegíveis de maior participação.
  3. O resto da capacidade é dividido pela participação, pelo método dos maiores restos (inteiros que somam exatamente o resto).
  4. Nenhum SKU passa do disponível. O excedente volta e é redistribuído entre os que ainda têm disponível, pela participação, até acabar a capacidade ou o disponível.
  5. Desempate pelo código do SKU, para o resultado ser estável.
  6. Sem venda nenhuma no produto, a divisão é igual entre os elegíveis.
- Rotas (papel `reposicao`; a participação também para `comprador`):
  - `GET /reposicao/produtos?busca=` lista os produtos com SKU ativo;
  - `GET /reposicao/produtos/{produto_id}/mix?capacidade=` devolve, para cada SKU, cor, tamanho, venda média diária, participação, disponível e quantidade sugerida. Sem `capacidade`, usa a gravada. Sem nenhuma das duas, devolve só a participação;
  - `PUT /reposicao/produtos/{produto_id}/capacidade` grava a capacidade.
- A participação entra na tela do SKU do comprador, ao lado das vendas mês a mês, com as outras cores e tamanhos do produto.
- UI: `gondola.html?produto=<id>`, mobile first, com o campo "Quantas peças cabem?" (preenchido com a capacidade gravada), a lista de SKUs com a quantidade em destaque e a participação. O painel do repositor ganha a aba "Montar gôndola" (busca de produto), e cada card de SKU ganha o link "Montar a gôndola deste produto".
- Isto é cálculo, sem Jev (ADR-0002).

### Seed e dados de demonstração

- `NOW` do seed passa a ser a data em que ele roda (truncada no dia), com o histórico gerado para trás. O seed continua reprodutível: mesma data, mesmo banco.
- Vendas diárias nos últimos 90 dias, uma linha por SKU e dia aberto, com domingos fechados. Antes disso continua o padrão mensal atual, para não inflar o banco.
- Produto novo "Tapete Banheiro", categoria `banho`, com a cor marrom, e cenários fixos e nomeados:
  - tapete marrom: λ perto de 10, ontem 5, hoje e anteontem conforme a regra, estoque alto. É o cenário de queda de venda com estoque;
  - um SKU em ruptura sem pedido;
  - um pedido `enviado` com data prevista 10 dias atrás, que contém um SKU em ruptura;
  - um SKU com queda de venda e disponível zero.
- O Tapete Banheiro tem 5 cores com participação bem diferente (marrom perto de 45%, branco perto de 8%), para o mix contar a história da reunião.
- `--skus N` gera N SKUs sintéticos a mais, para medir escala. O padrão continua perto de 80 SKUs.

### Documentação e domínio

- ADR-0006 e ADR-0007 escritas junto com esta spec. O glossário ganha os termos novos da linha "Vocabulário".
- README e roteiro de demo contam a história nova no último ticket.

## Testing Decisions

- Um bom teste exercita comportamento externo pela fronteira mais alta e asserta o que a pessoa veria: quem aparece em qual painel, em que ordem, com que motivo, o que uma ação muda e quem recebe qual notificação. Não testa função privada nem formato interno. O relógio é injetado em todo cenário com data.
- **Fronteiras**, as mesmas da spec 08, sem fronteira nova:
  1. **API HTTP** com `TestClient` e fakes em memória (ERP, política, repositórios, Jev, embedder), a fronteira principal. Testes novos para `/painel` com filtros e entregas atrasadas, `/estoque`, `/categorias`, `/pedidos/{id}/cobrancas`, `/fornecedores/{id}/atrasos`, `/notificacoes`, `/reposicao/painel`, `/skus/{sku}/verificacoes`, `/skus/{sku}/disponibilidade`, `/avisos/meus`, `/login`, `/usuarios`. Arte anterior: `src/api/tests/test_painel.py` com `cenario_painel.py`, `test_avisos.py` e `test_decisoes.py`.
  2. **UI estática**: o `tests/test_ui.py` passa a cobrir `login.html`, `usuarios.html`, `conta.html`, `estoque.html` e `reposicao.html`, e continua garantindo que todo `api(...)` aponta para uma rota que existe.
  3. **Contrato dos repositórios** (em memória e Postgres, a mesma suíte): usuários, sessões, cobranças, episódios, verificações, setores, avisos de gôndola e capacidades da gôndola. Arte anterior: os testes de contrato de avisos e decisões do módulo `painel`.
  4. **Contrato das leituras em lote do ERP**: a mesma suíte contra o adapter em memória e o Postgres, e a garantia de que o retrato em lote dá a mesma sugestão de pedido que a leitura por SKU, para os mesmos dados. Arte anterior: `src/erp_adapter/tests/`.
- Cenários obrigatórios:
  - **Ruptura**: SKU abaixo do piso de alerta aparece em "Em ruptura", SKU acima não aparece, disponível zero vem primeiro, e o lead time ignorado não gera `ruptura_antes_da_chegada`. A quantidade sugerida com `ignorar` bate com a conta da spec (exemplo numérico no teste). Uma versão de política gravada com `observado` continua calculando como antes.
  - **Notificação**: entrar em ruptura abre um episódio, varrer de novo não abre outro, sair fecha, voltar abre outro. Decisão vigente impede o episódio. O cursor separa lidas de não lidas. Duas varreduras simultâneas não duplicam (no Postgres).
  - **Entrega atrasada**: data prevista ontem com pendente entra, hoje não entra, sem data nunca entra e `recebido_total` nunca entra. A cobrança tira o pedido até a nova previsão, e a previsão vencida o traz de volta. Fornecedor com SKU em ruptura vem primeiro.
  - **Queda de venda**: o tapete marrom (λ 10, 5 e 0) entra. Um SKU com λ 0,3 e zero vendas não entra. Um domingo sem venda na loja inteira não conta. Com disponível zero e pedido atrasado, o SKU vai para entrega atrasada e não para o repositor. A verificação do dia tira o SKU, e um dia aberto a mais ainda parado o traz de volta. `sem_estoque_no_deposito` põe o SKU em estoque divergente no painel do comprador.
  - **Aviso de gôndola vazia**: o aviso põe o SKU no topo do painel do repositor e notifica o papel `reposicao`. A verificação fecha o aviso e notifica a vendedora autora. SKU com aviso e queda de venda aparece uma vez. O setor informado vira o setor conhecido do SKU e a verificação pode corrigi-lo. O filtro por setor funciona. `sem_estoque_no_deposito` com disponível no ERP vira estoque divergente, e com disponível zero não vira.
  - **Mix de gôndola**: com capacidade 12 e o tapete do seed, a soma dá 12, o marrom recebe mais e o branco recebe ao menos 1. Capacidade menor que o número de cores dá as peças aos que mais vendem. O disponível limita e o excedente é redistribuído. Produto sem venda divide igual. Sem capacidade, vem só a participação. A capacidade gravada é reusada.
  - **Permissões**: cada rota nova com 401 sem sessão e 403 com o papel errado. A vendedora não recebe preço de compra nem fornecedor em nenhuma rota que pode chamar.
  - **Escala**: o painel com o retrato em lote faz um número fixo de consultas, contadas com um listener do SQLAlchemy. O tempo com 5.000 SKUs é medido por um script de benchmark, não pela suíte, para a suíte não ficar lenta.
- Smoke tests contra o Postgres seguem `tests/smoke/test_painel.py`: login, ruptura com notificação, queda de venda com verificação e estoque divergente, aviso de gôndola vazia com verificação, e entrega atrasada com cobrança.
- Typecheck com pyright sem erro novo, testes por arquivo durante o trabalho e a suíte completa no fim de cada ticket.

## Out of Scope

- **Similar pelo ERP.** O botão da vendedora que leva ao produto semelhante ao que está faltando. Depende de dado que só existe no Maos. Fica no roadmap. A porta do ERP é o lugar dele (`similares_de(sku)`), quando houver integração.
- **Sazonalidade e volatilidade com machine learning** sobre 5 anos de vendas. O dev confirmou que fica para depois e que a sazonalidade segue como está (`periodo_sazonal` e meses quentes da política). Pré-requisito: histórico real de 5 anos, que só vem com o Maos.
- **Lead time real por fornecedor**, aprendido das entregas. A opção `ignorar` existe para a política voltar a usar lead time quando ele for confiável. O histórico de atrasos por fornecedor desta spec é o primeiro dado para isso.
- **Notificação fora do Copilot** (WhatsApp, e-mail, push do navegador) e o agendador em segundo plano que ela exige.
- **Integração com o Maos**, inclusive criar pedido de compra e ajustar estoque no ERP real. O Copilot continua só leitura (ADR-0005).
- **Estoque por local** (depósito e loja separados). O ERP fake tem um saldo só. A queda de venda é a forma de achar gôndola vazia sem esse dado.
- **Demanda não atendida** ("o cliente pediu e não tinha"), como registro separado do aviso. O aviso `acabou` cobre o caso por enquanto.
- **Recuperação de senha por e-mail.** O admin redefine a senha.
- **Multiempresa.** Um atacadista só (ADR-0003).
- **Mapa da loja ou planograma.** O setor é só um nome. Corredor, prateleira e posição ficam para quando o Maos (ou a loja) tiver esse dado.
- **Preço de venda para a vendedora.** O ERP fake não tem preço de venda no catálogo, só nas vendas.

## Further Notes

### Pormenores e suposições (escrito com o dev AFK, validar com o comprador)

Cada item abaixo é uma decisão tomada para não travar o desenvolvimento. Todos são parâmetro ou constante nomeada, fáceis de trocar, e devem entrar na lista de perguntas do onboarding (`.scratch/sugestao-compra/perguntas-comprador.md`).

1. **"Dias que o estoque precisa segurar" = piso de alerta.** Supomos que a regra do comprador é o piso de alerta que já existe (padrão 20 dias). Se ele quiser um número por categoria ou por SKU, isso vira outra spec, porque a política hoje é uma só.
2. **A sugestão de pedido também ignora o lead time.** O comprador falou da ruptura, mas manter o lead time na quantidade e tirar do alerta faria o alerta e a sugestão discordarem. Com `ignorar`, a compra pode chegar depois que o piso de reposição já foi consumido. O piso de reposição é a folga que absorve isso, então o comprador pode querer aumentá-lo.
3. **Entrega atrasada depende da data prevista.** No Maos, não sabemos se o pedido tem data prevista confiável. Pedido sem data nunca fica atrasado. Se o Maos não tiver essa data, a alternativa é "dias desde o envio maior que o lead time contratado", o que traz de volta o lead time que o comprador não confia.
4. **Dia aberto = a loja vendeu alguma coisa.** É uma heurística sem calendário. Um dia de sistema fora do ar também parece "loja fechada" e some da conta, o que é aceitável. Feriado com a loja aberta e vendendo pouco pode causar alarme falso.
5. **Sensibilidade da queda de venda** (2 dias, λ mínimo de 1 por dia, limiar de 0,01) é um chute com base no exemplo do tapete. A primeira semana de uso real deve calibrar esses números. As verificações `estava_na_gondola` são exatamente o dado de alarme falso para isso.
6. **"Dados que as vendedoras precisam" e "dados do comprador que ainda não mostramos"** não foram detalhados na reunião. Supomos para a vendedora: disponível, previsão de chegada e situação dos avisos dela. Para o comprador: a tela de Estoque, as entregas atrasadas e o histórico de atraso por fornecedor. Os dados que faltarem viram outra spec depois da próxima conversa com o comprador.
7. **Papéis fixos.** Quatro papéis com permissões no código, sem editor de permissões. Uma pessoa pode ter vários.
8. **Sessão de 30 dias** no celular da vendedora é conforto contra segurança. Se o celular for compartilhado, sair da conta resolve.
9. **Cobrança vale para o pedido inteiro**, não para o SKU. Supomos que o comprador cobra o pedido.
10. **Sem job em segundo plano.** As notificações nascem quando alguém abre o Copilot. O episódio guarda a hora da varredura que o abriu, que pode ser depois do momento real em que o SKU entrou em ruptura.
11. **Setor é uma lista do Copilot.** Não sabemos se o Maos tem setor por SKU. Supomos uma lista simples cadastrada pelo admin, e o Copilot aprende o setor de cada SKU pelos avisos e verificações. Se o Maos tiver o dado, ele substitui `setores_sku`.
12. **O aviso de gôndola exige o SKU.** O pedido foi "falar o setor e o SKU". Uma gôndola vazia sem saber qual SKU era (só o setor) não está coberta. O comentário serve de escape, mas o aviso precisa de um SKU.
13. **O mix de gôndola usa a venda passada sem corrigir a ruptura.** Se o marrom passou dias sem estoque ou com a gôndola vazia, a venda dele nesses dias foi zero, e a participação dele sai menor do que a demanda real. Corrigir isso exige reconstruir o estoque diário pelas movimentações e fica para depois da primeira validação.
14. **Capacidade por produto, não por SKU nem por tamanho.** Supomos que as cores e tamanhos de um produto dividem a mesma gôndola. Se cada tamanho tiver gôndola própria, o grupo passa a ser produto e tamanho.
15. **Ao menos uma peça por SKU com estoque** é uma regra de exposição suposta. O comprador pode preferir tirar da gôndola o que quase não vende.

### Roadmap

A ordem dos tickets segue as dependências técnicas e o valor para o comprador: fechar a spec 08, ruptura e usuários em paralelo, seed e escala, filtros e Estoque, entregas atrasadas, notificações, repositor e vendedora. Usuários vêm cedo para que cobranças, verificações e notificações já nasçam com o usuário logado, sem um passo intermediário com nome digitado. O que fica para depois está em `.scratch/plataforma/roadmap.md`.

### Fronteiras de teste

As fronteiras acima são as mesmas acordadas na spec 08. Não houve como confirmar com o dev, que estava AFK. A única fronteira nova proposta é o contrato das leituras em lote do ERP, que fica dentro do `erp_adapter`, como os contratos que ele já tem.
