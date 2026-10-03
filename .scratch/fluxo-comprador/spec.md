---
Status: ready-for-agent
Escopo: redesenho do fluxo do comprador chefe depois do feedback do comprador real (painel de alertas, aviso da equipe de vendas, tela do SKU, chat em contexto, decisão de compra)
Vocabulário: ver /CONTEXT.md
Decisões arquiteturais base: /docs/adr/0001-monolito-modular-por-dominio.md, /docs/adr/0002-jev-decide-codigo-executa-llm-redige.md, /docs/adr/0003-politica-de-compra-configuravel.md, /docs/adr/0005-copilot-termina-na-decisao-de-compra.md
Substitui: o fluxo de `.scratch/aprovacao/spec.md` (fila de aprovação, faixa de aprovação, pedido no ERP fake)
Origem: grilling com o dev em 2026-10-01, a partir do relato do comprador sobre compras de reposição e de cobertura
---

# Spec 08 - Fluxo do comprador: painel de alertas, aviso e decisão de compra

## Problem Statement

O comprador chefe olhou o Copilot e a tela principal não fez sentido para ele. Ela é uma fila de aprovação: um botão "Gerar sugestões", uma lista de sugestões e um par aprovar/rejeitar que cria pedido num ERP que não é o dele. O comprador não trabalha aprovando sugestões. O trabalho dele começa quando alguém ou alguma coisa avisa que um SKU vai faltar:

- **Compra de reposição**: uma vendedora da equipe de vendas fala que um SKU acabou ou está vendendo muito. Ele abre o giro no ERP, entende quando vai acabar (ou quanto vendia quando o estoque estava saudável), calcula quanto precisa e negocia com o representante. Se o representante sobe o preço, ele compara com outras peças.
- **Compra de cobertura**: ele roda um relatório no BI que mostra os SKUs que vão furar o estoque dentro do lead time. Só fica sabendo quando lembra de rodar o relatório.

Hoje o Copilot não sabe dos avisos da equipe de vendas, não mostra os alertas sozinho, espalha a informação de um SKU entre a fila e o chat, obriga o comprador a digitar o SKU no chat do zero e termina num "aprovar" que não corresponde a nada que ele faz. O pedido de verdade sai no Maos depois da negociação. O produto ficou engessado: telas separadas por tecnologia (fila, chat, política) em vez de por momento do trabalho do comprador.

## Solution

O Copilot passa a seguir o trabalho do comprador, do alerta à decisão (ADR-0005):

1. **Painel de alertas** como tela inicial. Junta, sem nenhum botão, os SKUs com aviso aberto da equipe de vendas e os SKUs com algum motivo de alerta da política (padrão: ruptura antes da chegada e abaixo do piso de alerta). É calculado na hora a partir do ERP fake. Os mais urgentes ficam no topo e cada linha abre a tela do SKU.
2. **Aviso da equipe de vendas**: página própria, feita para celular e sem login. A vendedora busca o SKU pelo nome, marca `acabou` ou `vendendo muito`, escreve um comentário se quiser e envia. O SKU entra no painel na hora, mesmo que o cálculo não veja problema.
3. **Tela do SKU**: tudo o que o comprador precisa para decidir num lugar só. Situação (estoque, giro, cobertura, em trânsito), vendas mês a mês, sugestão de pedido com memória de cálculo e alertas, sinais do corpus, avisos abertos, histórico de preço pago por fornecedor e substitutos com o preço atual, para a negociação com o representante.
4. **Chat em contexto**: o chat vira um painel lateral presente em todas as telas do comprador. Na tela do SKU, ele já sabe de qual SKU se trata, então "por que está acabando?" funciona sem citar o produto.
5. **Decisão de compra** encerra o fluxo: `vou_comprar` (com quantidade), `negociando` ou `nao_comprar_agora` (com motivo). Ela fecha os avisos abertos do SKU e tira o SKU do painel por 7 dias, a não ser que chegue um aviso novo. O Copilot não cria pedido de compra.

Saem a fila de aprovação, a faixa de aprovação e a criação de pedido de compra no ERP fake. O ERP fake volta a ser só leitura para o Copilot.

## User Stories

### Comprador chefe: painel de alertas

1. Como comprador chefe, quero abrir o Copilot e ver de cara os SKUs que pedem atenção, para não depender de lembrar de rodar o relatório do BI.
2. Como comprador chefe, quero que o painel apareça sem eu apertar "gerar", para que abrir o Copilot já seja olhar o estado atual.
3. Como comprador chefe, quero ver no topo os SKUs com aviso da equipe de vendas ou com ruptura antes da chegada, para atacar primeiro o que vai faltar na loja.
4. Como comprador chefe, quero que, dentro de cada grupo, os SKUs venham do menor para o maior em cobertura na chegada sem a compra, para ver primeiro o que acaba antes.
5. Como comprador chefe, quero ver em cada linha o nome do produto, a cor, o tamanho, o disponível, a cobertura atual e a cobertura na chegada sem a compra, para entender o tamanho do problema sem abrir o SKU.
6. Como comprador chefe, quero ver em cada linha os motivos pelos quais o SKU está no painel (aviso, ruptura antes da chegada, abaixo do piso de alerta e os outros que eu escolhi), para saber por que estou olhando para ele.
7. Como comprador chefe, quero ver em cada linha quantos avisos abertos o SKU tem, o tipo do último e quem avisou, para saber se a equipe de vendas está insistindo.
8. Como comprador chefe, quero ver na linha a quantidade sugerida e o fornecedor da sugestão de pedido quando houver compra, para ter uma ideia do tamanho da compra antes de abrir.
9. Como comprador chefe, quero clicar numa linha e cair na tela do SKU, para decidir ali.
10. Como comprador chefe, quero que um SKU com aviso aberto apareça no painel mesmo quando o cálculo diz que não precisa comprar, porque a vendedora pode estar vendo algo que o histórico não mostra.
11. Como comprador chefe, quero que o painel deixe claro quando um SKU está lá só por aviso, sem motivo de alerta calculado, para eu saber que o número e a loja discordam.
12. Como comprador chefe, quero que o SKU suma do painel depois de eu registrar uma decisão de compra, para o painel mostrar só o que ainda está em aberto.
13. Como comprador chefe, quero que o SKU volte ao painel 7 dias depois da decisão se o problema continuar, para nada ficar esquecido.
14. Como comprador chefe, quero que o SKU volte ao painel na hora se a equipe de vendas mandar um aviso novo depois da minha decisão, porque é informação nova.
15. Como comprador chefe, quero ver numa seção separada do painel os SKUs que eu decidi nos últimos 7 dias (com a decisão e a data), para acompanhar o que está em negociação.
16. Como comprador chefe, quero ver uma mensagem clara quando não houver nenhum SKU pedindo atenção, para saber que o painel funcionou e está tudo em ordem.
17. Como comprador chefe, quero ver uma mensagem clara quando o ERP fake estiver fora do ar, em vez de um "erro 500", para saber que o problema é de infraestrutura e não do estoque.
18. Como comprador chefe, quero escolher na política de compra quais alertas põem um SKU no painel, para o painel refletir o meu jeito de comprar.
19. Como comprador chefe, quero que SKU inativo nunca apareça no painel, porque não compro mais.

### Equipe de vendas: aviso

20. Como vendedora da equipe de vendas, quero abrir uma página pelo celular e avisar o comprador em poucos toques, para não precisar parar o atendimento.
21. Como vendedora, quero buscar o SKU digitando parte do nome do produto, a cor ou o tamanho, sem me preocupar com acento ou maiúscula, porque não sei o código do SKU.
22. Como vendedora, quero ver na busca o nome do produto, a cor e o tamanho de cada resultado, para escolher o SKU certo entre as variações.
23. Como vendedora, quero escolher entre `acabou` e `vendendo muito`, porque são as duas coisas que eu percebo no balcão.
24. Como vendedora, quero escrever um comentário opcional ("cliente X quer 200 peças"), para dar contexto ao comprador.
25. Como vendedora, quero informar meu nome, para o comprador saber com quem falar.
26. Como vendedora, quero que o celular lembre meu nome, para não digitar de novo em cada aviso.
27. Como vendedora, quero ver a confirmação de que o aviso foi enviado, para ter certeza de que o comprador vai ver.
28. Como vendedora, quero conseguir mandar outro aviso logo depois do primeiro, sem recarregar a página, para avisar vários SKUs seguidos.
29. Como vendedora, quero que a página de aviso não mostre o painel, a política nem o chat, porque não preciso deles e eles atrapalham no celular.
30. Como vendedora, quero ser impedida de avisar sobre um SKU inativo, para não pedir algo que não se compra mais.

### Comprador chefe: tela do SKU

31. Como comprador chefe, quero ver na tela do SKU o nome, a cor, o tamanho e o código, para ter certeza do que estou olhando.
32. Como comprador chefe, quero ver o disponível, o em trânsito, a posição, o giro e a cobertura, para fazer o que hoje faço abrindo o giro no ERP.
33. Como comprador chefe, quero ver as vendas mês a mês dos últimos 12 meses, para enxergar se o SKU está acelerando e se houve meses de ruptura.
34. Como comprador chefe, quero ver a sugestão de pedido com quantidade, fornecedor, valor estimado e memória de cálculo, para conferir a conta.
35. Como comprador chefe, quero ver os alertas da sugestão de pedido, para não ser surpreendido por ruptura, teto, pedido mínimo, lead time ou período sazonal.
36. Como comprador chefe, quero ver o motivo quando a sugestão de pedido for zero, para saber se é SKU novo, sem giro, sem fornecedor ou acima do ponto de reposição.
37. Como comprador chefe, quero ver os sinais do corpus (atraso do fornecedor, demanda sazonal, encalhe) com os trechos de origem, para usar o que a empresa já registrou.
38. Como comprador chefe, quero que a tela do SKU abra mesmo quando o Jev estiver fora do ar, mostrando que os sinais estão indisponíveis, para eu não ficar bloqueado.
39. Como comprador chefe, quero que os sinais do corpus carreguem depois do resto, para a tela não ficar parada esperando o Jev.
40. Como comprador chefe, quero ver os avisos abertos do SKU com tipo, comentário, quem avisou e quando, para saber o que a equipe de vendas está dizendo.
41. Como comprador chefe, quero ver o histórico de preço unitário que o atacadista pagou por esse SKU em cada pedido de compra, com fornecedor e data, para responder ao representante que quer subir o preço.
42. Como comprador chefe, quero ver o preço atual de cada fornecedor do SKU, para comparar com o que paguei antes.
43. Como comprador chefe, quero ver os substitutos do SKU (outros produtos da mesma categoria e tamanho) com o menor preço atual e o fornecedor, para ter referência na negociação.
44. Como comprador chefe, quero ver as decisões de compra que já registrei para o SKU, para lembrar o que combinei da última vez.
45. Como comprador chefe, quero registrar `vou_comprar` com a quantidade, já preenchida com a sugestão e editável, para guardar o que vou pedir no Maos.
46. Como comprador chefe, quero registrar `negociando` com um comentário opcional, para tirar o SKU do painel enquanto converso com o representante.
47. Como comprador chefe, quero registrar `nao_comprar_agora` com um motivo obrigatório, para lembrar depois por que deixei passar.
48. Como comprador chefe, quero informar meu nome na decisão de compra, para ficar registrado quem decidiu.
49. Como comprador chefe, quero que registrar a decisão feche os avisos abertos do SKU, para a equipe de vendas e eu sabermos que o aviso foi tratado.
50. Como comprador chefe, quero voltar ao painel depois de decidir e ver o SKU fora da lista, para seguir para o próximo.
51. Como comprador chefe, quero abrir a tela do SKU direto por um link, para mandar a alguém ou abrir pelo chat.
52. Como comprador chefe, quero ver uma mensagem clara quando o SKU do link não existir.

### Comprador chefe: chat em contexto

53. Como comprador chefe, quero o chat num painel lateral em todas as minhas telas, para perguntar sem sair do que estou fazendo.
54. Como comprador chefe, quero que o chat na tela do SKU responda sobre esse SKU quando eu não citar outro produto, para perguntar "por que está acabando?" sem repetir o nome.
55. Como comprador chefe, quero que, se eu citar outro produto na pergunta, o chat responda sobre o produto citado e não sobre o da tela, para poder comparar.
56. Como comprador chefe, quero ver no chat qual SKU está em contexto, para entender sobre o que ele vai responder.
57. Como comprador chefe, quero que o chat no painel funcione como hoje, sem SKU em contexto, para perguntas gerais sobre política e fornecedores.
58. Como comprador chefe, quero que o registro de decisão do chat guarde o SKU em contexto, para a auditoria saber de onde a resposta veio.
59. Como comprador chefe, quero abrir e fechar o painel do chat, para ter espaço na tela quando não estiver usando.
60. Como comprador chefe, quero que no celular o chat abra em tela cheia, para conseguir ler e digitar.
61. Como comprador chefe, quero que as citações, os sinais e as fichas continuem aparecendo nas respostas do chat lateral como na tela de chat antiga, para não perder nada do que já funcionava.

### Comprador chefe: política

62. Como comprador chefe, quero marcar na tela de política os motivos de alerta que põem um SKU no painel, para ajustar o painel ao meu jeito.
63. Como comprador chefe, quero que a tela de política não mostre mais os limites das faixas de aprovação, porque o Copilot não aprova pedidos.
64. Como comprador chefe, quero que mudar os motivos de alerta mude o painel na próxima vez que eu abrir, porque o painel é calculado na hora com a política ativa.

### Dev e auditoria

65. Como dev, quero que o Copilot não escreva mais pedidos de compra no ERP fake, para o ERP ser só leitura e a demo não criar dados que ninguém lança no Maos.
66. Como dev, quero que avisos e decisões de compra fiquem guardados no schema do Copilot, com migration, para sobreviverem a reinícios.
67. Como dev, quero que a decisão de compra guarde a quantidade sugerida e a versão da política no momento da decisão, para comparar depois o que o Copilot sugeriu com o que o comprador decidiu.
68. Como dev, quero que a fila de aprovação, a faixa de aprovação e as rotas de sugestões sumam do código, dos testes e da UI, para não manter um fluxo que ninguém usa.
69. Como dev, quero que o README e o roteiro de demo descrevam o fluxo novo, para quem avaliar o projeto ver o produto atual.
70. Como dev, quero um smoke test contra o Postgres que cubra aviso, painel e decisão, como os smoke tests atuais.

## Implementation Decisions

### Módulo novo `painel` (substitui `aprovacao`)

- Um módulo de domínio que é dono dos **avisos**, das **decisões de compra** e da composição do **painel de alertas**. Segue o padrão dos módulos atuais: schemas, service, repositório como Protocol, versão em memória, versão Postgres e dependências do FastAPI.
- Interface do service:
  - `registrar_aviso(sku_code, tipo, avisado_por, comentario?) -> Aviso`. Lança erro de SKU inexistente (404) e de SKU inativo (422).
  - `registrar_decisao(sku_code, tipo, decidido_por, quantidade?, motivo?, comentario?) -> DecisaoCompra`. Valida que `vou_comprar` tem quantidade maior que zero e que `nao_comprar_agora` tem motivo. Calcula a sugestão de pedido do momento para guardar `quantidade_sugerida` e `politica_versao`.
  - `avisos_abertos(sku_code) -> list[Aviso]` e `decisoes(sku_code) -> list[DecisaoCompra]`, as mais recentes primeiro.
  - `painel() -> Painel` com duas listas: `alertas` e `decididos`.
- **Aviso aberto** é derivado, sem coluna de status: um aviso está aberto se não existe decisão de compra do mesmo SKU registrada depois dele. Por isso a decisão "fecha" os avisos sem precisar atualizá-los.
- **Decisão vigente**: a decisão mais recente do SKU, registrada há menos de 7 dias, sem aviso posterior a ela. O prazo é uma constante nomeada no módulo. Não é parâmetro da política nesta spec.
- **Composição do painel**, para cada SKU ativo:
  - Calcula a sugestão de pedido com a política ativa e a cobertura atual.
  - Motivos do SKU: os alertas da sugestão cujo tipo está nos motivos de alerta da política, mais `abaixo_do_piso_alerta` quando a cobertura atual (só o disponível) está abaixo do piso de alerta e esse motivo está na política.
  - O SKU entra no painel se tem aviso aberto ou ao menos um motivo.
  - Se tem decisão vigente, vai para `decididos` em vez de `alertas`.
  - Ordem de `alertas`: primeiro os com aviso aberto ou ruptura antes da chegada, depois o resto. Dentro de cada grupo, a menor cobertura na chegada sem a compra primeiro. SKUs sem cálculo (SKU novo, sem giro, sem fornecedor) ficam no fim do grupo. Desempate pelo código do SKU, para a ordem ser estável.
  - O painel não chama o Jev. Os sinais do corpus ficam na tela do SKU.
- Cada item de `alertas` traz o SKU (código, produto, cor, tamanho), disponível, cobertura atual, cobertura na chegada sem a compra, motivos, quantidade e fornecedor sugeridos (quando houver compra), número de avisos abertos e o último aviso. Cada item de `decididos` traz o SKU e a decisão vigente.
- Um SKU que lança `SKUSemEstoque` ao calcular é pulado no painel, com o código listado num campo `skus_com_erro`, para um dado quebrado não derrubar o painel inteiro.

### Esquema (schema `copilot`, uma migration)

- Tabela `avisos`: id, sku_code, tipo (`acabou` | `vendendo_muito`), comentario (opcional), avisado_por, criado_em. Índice por (sku_code, criado_em).
- Tabela `decisoes_compra`: id, sku_code, tipo (`vou_comprar` | `negociando` | `nao_comprar_agora`), quantidade (opcional), motivo (opcional), comentario (opcional), decidido_por, quantidade_sugerida, politica_versao, criado_em. Índice por (sku_code, criado_em). Check constraints espelham as validações do service.
- Remove a tabela `sugestoes_fila`.
- Política de compra: renomeia `motivos_de_destaque` para `motivos_de_alerta` e remove `faixa_1_ate_reais`, `faixa_2_ate_reais` e `faixa_3_ate_reais` de todas as versões. Nas versões existentes, os valores de motivo que vinham do corpus (`atraso_do_fornecedor`, `demanda_sazonal`, `encalhe`) são descartados e `abaixo_do_piso_alerta` é acrescentado. O padrão passa a ser `ruptura_antes_da_chegada` e `abaixo_do_piso_alerta`.
- `registros_decisao` (chat) ganha `sku_em_contexto` opcional.

### Política de compra

- `MotivoDestaque` vira `MotivoAlerta`, com os valores de `TipoAlerta` mais `abaixo_do_piso_alerta`. Os motivos do corpus saem porque o painel não chama o Jev.
- Saem os campos e as validações das faixas. `GET/PUT /politica-compra` refletem isso. É uma quebra de contrato aceita, porque o único cliente é a UI do próprio projeto.

### `purchasing`

- Saem `faixa_aprovacao`, `FaixaAprovacao`, o cálculo de faixas e `submeter_pedido`.
- Entra `referencias_de_preco(sku_code)`, que devolve:
  - o histórico de preço: um item por item de pedido de compra do SKU no ERP fake, com data do pedido, fornecedor, preço unitário em centavos, quantidade e status do pedido, do mais recente para o mais antigo, ignorando pedidos cancelados;
  - o preço atual de cada fornecedor do SKU;
  - os substitutos: SKUs ativos de outro produto, mesma categoria e mesmo tamanho, cada um com o menor preço atual entre os fornecedores dele e o nome desse fornecedor, ordenados por preço e limitados a 10.
- Os preços seguem a convenção atual: o campo chamado reais guarda centavos.

### `erp_adapter`

- Sai `criar_pedido_compra` da porta e das duas implementações. Sai também `fornecedor_tem_pedido` se, depois da remoção da faixa, ninguém mais usar.
- Entra `itens_de_pedido_de(sku_code)`, leitura dos itens de pedido de compra do SKU com o cabeçalho do pedido (data, fornecedor, status). Implementado em memória e no Postgres.

### `catalog`

- Entra `buscar_skus(texto, limite=20)`: SKUs ativos cujo código, nome do produto, cor ou tamanho contêm todas as palavras do texto, sem diferenciar acento nem maiúscula. Ordem: nome do produto, cor, tamanho.

### `ai` (chat)

- `Copilot.responder` ganha `sku_em_contexto` opcional. A intenção continua com o Jev e a regra é do código: quando a intenção é `situacao_sku` ou `sugestao_compra`, a identificação não acha nenhum SKU na pergunta e existe SKU em contexto, a identificação passa a ser o SKU em contexto, marcada com a origem `contexto`. Se a pergunta cita um produto, vale o citado. Nas outras intenções, o contexto é ignorado.
- O registro de decisão grava o `sku_em_contexto`. Os scripts de avaliação continuam chamando sem contexto.

### API

- Novas rotas:
  - `GET /painel`
  - `POST /avisos` com corpo `{sku_code, tipo, avisado_por, comentario?}`, que responde 201
  - `GET /skus?busca=<texto>`, a busca da página de aviso, com `busca` obrigatória e de pelo menos 2 caracteres
  - `GET /skus/{sku_code}/avisos`, que devolve os abertos
  - `GET /skus/{sku_code}/decisoes`
  - `POST /skus/{sku_code}/decisoes`, que responde 201, 404 sem o SKU e 422 nas validações
  - `GET /skus/{sku_code}/precos`
- A tela do SKU reaproveita as rotas que já existem: análise, sugestão de compra, sinais da sugestão e vendas.
- `POST /chat` aceita `sku_code` opcional no corpo. SKU desconhecido no contexto responde 404.
- Sai todo o router `/sugestoes`.
- Com o banco fora do ar, `GET /painel` responde 503 com mensagem, como o health, em vez de 500.

### UI (estática, servida em `/ui`, sem build)

- `index.html` vira o **painel de alertas**, com a seção "Decididos nos últimos 7 dias" recolhida por padrão.
- `sku.html?sku=<código>` é a **tela do SKU**. Os blocos carregam em paralelo e os sinais do corpus chegam por último, sem bloquear o resto. O formulário de decisão de compra muda os campos conforme o tipo e, depois de enviar, volta ao painel.
- `aviso.html` é a página da **equipe de vendas**: mobile first, sem navegação e sem chat. Tem busca com debounce, escolha do tipo em dois botões grandes, comentário, nome lembrado no `localStorage` (com try/catch) e confirmação na própria página.
- `politica.html` fica, sem os campos de faixa e com os motivos de alerta.
- `chat.html` sai. O chat vira um componente lateral montado pelo painel, pela tela do SKU e pela política, que recebe o SKU em contexto da página e mostra qual é. No celular, abre em tela cheia. Reaproveita a renderização atual de resposta, citações, fichas e sugestões.
- A navegação do comprador fica Painel e Política, com o botão do chat no cabeçalho. A página de aviso tem link próprio, para ser compartilhado com a equipe de vendas.
- `fila.js` sai.

### Documentação

- README e roteiro de demo descrevem o fluxo novo: aviso pelo celular, painel, tela do SKU, chat em contexto e decisão. As screenshots da fila são trocadas.

## Testing Decisions

- Um bom teste exercita comportamento externo pela fronteira mais alta, ou seja, HTTP com `TestClient` e dependências trocadas por fakes em memória (ERP, política, repositórios do painel, Jev, embedder). Não testa função privada nem formato interno. Asserta o que o comprador veria: quem está no painel, em que ordem, com que motivos, e o que a decisão muda.
- **Fronteiras acordadas com o dev:**
  1. **API HTTP**, a fronteira principal. Testes novos para `/painel`, `/avisos`, `/skus?busca`, `/skus/{sku}/avisos`, `/skus/{sku}/decisoes`, `/skus/{sku}/precos` e `POST /chat` com `sku_code`. Arte anterior: os testes HTTP atuais da fila (cenário `URGENTE`/`REGULAR`/`SOBRANDO` com giro e fornecedor fixos e relógio injetado), de SKUs e do chat.
  2. **UI estática**: o teste atual de UI passa a cobrir `index.html`, `sku.html`, `aviso.html` e `politica.html`, e continua garantindo que todo `api(...)` dos `.js` aponta para uma rota que existe. Isso pega chamada órfã para `/sugestoes`.
  3. **Contrato dos repositórios** de avisos e decisões, com a mesma suíte rodando contra a versão em memória e a Postgres. Arte anterior: o teste de contrato da fila.
- Cenários obrigatórios do painel:
  - SKU com ruptura antes da chegada aparece antes de SKU só abaixo do piso.
  - SKU sem motivo e sem aviso não aparece.
  - SKU com aviso e sem motivo aparece no primeiro grupo.
  - Decisão tira o SKU de `alertas` e põe em `decididos`.
  - Aviso posterior à decisão traz o SKU de volta.
  - Decisão com mais de 7 dias, com relógio injetado, não vale mais.
  - Motivo fora da política não põe o SKU no painel.
  - SKU inativo nunca aparece.
  - SKU com estoque quebrado vai para `skus_com_erro` sem derrubar o painel.
- Cenários do chat em contexto, com Jev fake:
  - Sem produto na pergunta, usa o contexto.
  - Com produto citado, usa o citado.
  - Intenção `politica_ou_fornecedor` ignora o contexto.
  - O registro grava o contexto.
- Saem os testes de `aprovacao`, de faixa e de `submeter_pedido`. Os testes de `purchasing` e de `politica_compra` são ajustados para o campo novo.
- Smoke test contra o Postgres: o atual da fila é trocado por um que registra um aviso, confere o SKU no painel, registra a decisão e confere a saída do painel.
- Rodar typecheck, testes por arquivo durante o trabalho e a suíte completa no fim.

## Out of Scope

- Notificação fora do Copilot (e-mail, WhatsApp, push). O painel é o único canal no MVP.
- Integração com o WhatsApp para os avisos.
- Login e papéis. Equipe de vendas e comprador chefe informam o nome à mão, como já acontece na aprovação.
- Preço de mercado de outros atacadistas. Não há fonte de dado.
- Compra de produto novo (visita do representante com produto que o atacadista ainda não vende).
- Giro ajustado por ruptura ("média de quando o estoque estava saudável") e ciclo de compra por SKU. São regras de cálculo que ficam para quando o comprador usar a plataforma. O padrão do ciclo de compra passa a 2 meses (ver Further Notes).
- Criar pedido de compra em qualquer ERP.
- Histórico ou sessão de conversa no chat lateral. Cada pergunta continua independente.
- Prazo da decisão vigente como parâmetro da política.

## Further Notes

- O dev pediu, para o MVP, ciclo de compra padrão de 2 meses ("no mínimo 60 dias de cobertura de venda"). A validação da política exige `piso_reposicao_dias / 30 + ciclo_compra_meses <= teto_meses`. Com piso de 30 dias e teto de 3 meses, um ciclo de 2 meses fecha exatamente no limite. Trocar o padrão para 2 meses entra nesta spec, na mesma migration da política (só a versão padrão. Versões gravadas pelo comprador não mudam).
- A equipe de vendas é o primeiro usuário do Copilot que não é o comprador chefe. A página de aviso precisa ser utilizável num celular comum, com alvos de toque grandes e sem rolagem horizontal.
- O tempo do painel cresce com o número de SKUs ativos, porque calcula a sugestão de cada um. Com o seed atual é aceitável. Se ficar lento, o caminho é cache por requisição no adapter Postgres, não pré-calcular e guardar (o painel não guarda estado por decisão desta spec).
- O glossário já foi atualizado com Aviso, Motivo de alerta, Painel de alertas, Decisão de compra, Substituto, Representante e Equipe de vendas.
