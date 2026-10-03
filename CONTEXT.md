# Copilot de Compras

Aplicação de aprendizado de arquitetura que ajuda o atacadista de cama, mesa e banho da família a decidir compras (o que comprar, quanto, de quem e quando), usando LLM com RAG e tool use sobre dados de um ERP simulado.

## Language

### Negócio

**Atacadista**:
A empresa da família que compra de fornecedores e revende ao pequeno varejo. Segmento: cama, mesa e banho.
_Avoid_: distribuidora, revendedor (são outras figuras), atacado, "loja".

**Fornecedor**:
Empresa (normalmente fábrica ou importadora têxtil) da qual o atacadista compra produtos pra revender. Ver `corpus/fornecedores/` pros fornecedores sintéticos usados.
_Avoid_: vendor, parceiro, indústria.

**Representante**:
Vendedor de um fornecedor que visita o comprador chefe pra apresentar produtos e negociar preço. É com ele que o comprador fecha a compra.
_Avoid_: vendedor (é ambíguo com a equipe de vendas), fornecedor (é a empresa, não a pessoa).

**Equipe de vendas**:
Vendedoras da loja física do atacadista, que atendem os varejistas e vendem o que o comprador chefe comprou. São as primeiras a perceber que um SKU acabou ou está vendendo acima do normal.
_Avoid_: vendedor (sozinho), time comercial.

**SKU**:
Unidade individual comercializável, definida por combinação de modelo, cor, tamanho e material. Ex: "Toalha Banho Conforto Bege 70x140". Um mesmo produto de catálogo pode ter dezenas de SKUs.
_Avoid_: produto (impreciso), item.

**Pedido de compra**:
Compromisso formal do atacadista com um fornecedor pra receber quantidades específicas de SKUs em uma data futura, sob condições comerciais definidas (preço, prazo de pagamento, frete).
_Avoid_: purchase order (usar em inglês só em código quando for API/DTO), ordem de compra, encomenda.

**Comprador chefe**:
Quem decide as compras no atacadista. Define a política de compra, negocia com os representantes e decide cada pedido de compra. Não é o desenvolvedor do Copilot.
_Avoid_: usuário (genérico demais), cliente (é o varejista).

**Copilot**:
A aplicação em si. Um assistente que sugere decisões de compra a partir de dados do ERP fake e do corpus de documentos, sempre com o comprador chefe decidindo no fim.
_Avoid_: agente autônomo (não é autônomo por design - human-in-the-loop é premissa), assistente.

### Métricas de estoque

**Giro**:
Vendas médias de um SKU por mês, calculado como média móvel dos últimos 6 meses. Base pra todo dimensionamento de compra.
_Avoid_: rotatividade, vendas médias, saída.

**Cobertura**:
Estoque atual dividido pelo giro, expresso em meses. "SKU X tem 2.3 meses de cobertura" = com o giro atual, o estoque atende 2.3 meses. O domínio guarda meses. Para as pessoas, a cobertura aparece em dias (ver Cobertura em dias).
_Avoid_: dias de estoque (use cobertura em dias).

**Venda média diária**:
Giro dividido por 30. É a unidade em que o comprador chefe pensa a ruptura.
_Avoid_: giro diário, média de vendas.

**Cobertura em dias**:
A cobertura expressa em dias: disponível dividido pela venda média diária. "Segura 12 dias". É como a UI mostra a cobertura ao comprador, à equipe de vendas e ao repositor. Ver ADR-0006.
_Avoid_: dias de estoque, autonomia.

**Ruptura**:
Na linguagem do comprador chefe, o SKU está em ruptura quando a cobertura em dias fica abaixo do piso de alerta (os dias de venda que o estoque precisa segurar). No código, é o motivo de alerta `abaixo_do_piso_alerta`. Com disponível zero, a ruptura já é falta na loja. Não depende do lead time (ADR-0006).
_Avoid_: ruptura antes da chegada (é outro alerta, só com lead time ligado), falta, estoque zerado.

**Lead time**:
Prazo entre colocar um pedido de compra e receber a mercadoria no CD. Contratual vs observado é uma distinção que importa (ver reunião Q1/2025 no corpus). O comprador não confia nele, e por padrão a política o ignora (ADR-0006).
_Avoid_: prazo de entrega (ambíguo - pode significar do atacadista pro varejista).

**Ficha (do SKU)**:
Composição de leitura que devolve o estado atual de um SKU pronto pra decisão de compra - dados do catálogo, estoque atual, giro, cobertura e fornecedores disponíveis. Materializada no módulo `ficha_sku` e servida pelo endpoint `/skus/{sku_code}/analise`.
_Avoid_: análise (ambíguo), dashboard, resumo.

**Em trânsito**:
Quantidade de um SKU que ainda falta chegar de pedidos de compra `aprovado`, `enviado` ou `recebido_parcial`. Rascunho e cancelado não contam.
_Avoid_: a receber, pendente, pedido em aberto (é o documento, não a quantidade).

**Posição (de estoque)**:
Estoque disponível mais o que está em trânsito. É a base da sugestão de pedido. A cobertura continua usando só o disponível.
_Avoid_: estoque total, saldo.

### Compra

**Política de compra**:
Conjunto versionado de parâmetros definidos pelo comprador chefe (teto, pisos, ciclo de compra, lead time base, critério de fornecedor, sazonalidade, regra de SKU novo, motivos de alerta) que a sugestão de pedido e o painel de alertas usam. É a fonte da verdade do cálculo. O documento de política no corpus é só contexto. Ver ADR-0003.
_Avoid_: regras, configuração, estratégia.

**Teto**:
Cobertura máxima, em meses, que o SKU pode ter quando a compra chega. Parâmetro da política (R1).
_Avoid_: estoque máximo, limite.

**Piso de alerta**:
Cobertura, em dias, abaixo da qual o SKU está em ruptura: os dias de venda que o estoque precisa segurar. Parâmetro da política (R4).
_Avoid_: piso (sozinho é ambíguo), estoque mínimo.

**Piso de reposição**:
Cobertura, em dias, que o comprador quer ainda ter quando a compra chega, como folga. Parâmetro da política (R4).
_Avoid_: estoque de segurança, piso (sozinho).

**Ponto de reposição**:
Momento em que o estoque previsto na chegada da compra fica abaixo do piso de reposição. A partir dele a sugestão de pedido passa a ter quantidade maior que zero.
_Avoid_: gatilho, ponto de pedido.

**Ciclo de compra**:
Meses de giro que cada compra cobre além do piso de reposição. Parâmetro da política.
_Avoid_: frequência, periodicidade.

**Sugestão de pedido**:
Resultado determinístico de `purchasing` para um SKU: quantidade, fornecedor, memória de cálculo, alertas e versão da política usada. Quando não há compra, quantidade zero com motivo. Nunca vira pedido de compra dentro do Copilot: o comprador chefe negocia com o representante e lança o pedido no ERP real.
_Avoid_: recomendação, pedido sugerido, proposta.

**Aviso (da equipe de vendas)**:
Recado da equipe de vendas sobre um SKU: `acabou` ou `vendendo muito`, com comentário opcional e o nome de quem avisou. Fica aberto até o comprador chefe registrar uma decisão de compra para o SKU. É um sinal humano e põe o SKU no painel mesmo quando o cálculo não vê problema.
_Avoid_: alerta (é o que o `purchasing` calcula), pedido, solicitação, chamado.

**Motivo de alerta**:
Alerta do `purchasing` que o comprador chefe escolheu, na política de compra, para pôr um SKU no painel de alertas. Padrão: ruptura (abaixo do piso de alerta). Ruptura antes da chegada só faz sentido com o lead time ligado (ADR-0006).
_Avoid_: prioridade, risco (genérico demais), motivo de destaque (nome antigo, da fila de aprovação).

**Painel de alertas**:
Tela inicial do comprador chefe. Lista os SKUs que pedem atenção agora: os que têm aviso aberto ou algum motivo de alerta. Vêm primeiro os com aviso, depois os em ruptura (disponível zero no topo e, em seguida, a menor cobertura em dias), os que acabam antes da compra chegar (quando a política usa o lead time) e os outros motivos. É calculado na hora a partir do ERP fake e não guarda estado próprio. Um SKU some do painel enquanto houver decisão de compra vigente e nenhum aviso novo.
_Avoid_: dashboard, fila, caixa de entrada, relatório (é o que o BI emite sob demanda).

**Decisão de compra**:
O que o comprador chefe registra no Copilot depois de olhar um SKU: `vou_comprar` (com quantidade), `negociando` ou `nao_comprar_agora` (com motivo). Fecha os avisos abertos do SKU e o tira do painel por um prazo. Não cria pedido de compra.
_Avoid_: aprovação (o Copilot não aprova nada), pedido, registro de decisão (é o do chat).

**Substituto**:
SKU ativo de outro produto, da mesma categoria e tamanho, que o comprador chefe pode usar como referência de preço quando o representante quer subir o preço.
_Avoid_: concorrente (o comprador usa, mas é ambíguo com outro atacadista), similar, equivalente.

**Sinal (do corpus)**:
O que os documentos do corpus relatam sobre o fornecedor e o produto de uma sugestão de pedido: atraso do fornecedor, venda forte do produto numa época do ano ou encalhe do produto (ou da categoria dele) numa compra anterior. O Jev responde trecho a trecho e o código transforma em sinal o que passa do limiar, com os trechos de origem. Acompanha a sugestão e nunca altera a quantidade.
_Avoid_: alerta (é o que o `purchasing` calcula a partir do ERP), insight, risco.

**Onboarding**:
Sequência de perguntas em linguagem de comprador que preenche a política de compra. Rascunho em `.scratch/sugestao-compra/perguntas-comprador.md`.
_Avoid_: setup, configuração inicial.

**Similar**:
Função do ERP real (Maos) que aponta um produto semelhante ao que está faltando, para a vendedora oferecer ao cliente. Ainda não existe no Copilot: depende da integração com o Maos.
_Avoid_: substituto (é a referência de preço do comprador, outro uso), equivalente.

**Entrega atrasada**:
Item de pedido de compra `aprovado`, `enviado` ou `recebido_parcial` com quantidade pendente e data prevista de entrega já vencida. É motivo de alerta. No painel aparece agrupada por fornecedor, porque o comprador cobra o fornecedor, não o SKU.
_Avoid_: atraso do fornecedor (é o sinal do corpus), pedido atrasado.

**Cobrança de entrega**:
O que o comprador chefe registra depois de cobrar o fornecedor por um pedido de compra com entrega atrasada, com nova previsão opcional. Tira o pedido do painel até a nova previsão ou por um prazo. Fica no Copilot: o ERP não muda.
_Avoid_: follow-up, reclamação.

### Operação da loja

**Repositor**:
Pessoa que leva a mercadoria do depósito para a gôndola da loja física. Não compra nada.
_Avoid_: estoquista, reposição (sozinho é ambíguo com compra de reposição).

**Gôndola**:
Onde o SKU fica exposto na loja física. O ERP só tem um saldo de estoque, sem separar gôndola e depósito.
_Avoid_: prateleira, exposição, loja (sozinho).

**Queda de venda**:
SKU que vende com regularidade e cuja venda nos últimos dias abertos ficou muito abaixo do esperado pela venda diária base, calculado em código com limiares da política. Com estoque disponível, a suspeita é gôndola vazia e o SKU vai para o painel do repositor. Sem estoque, vira ruptura ou entrega atrasada para o comprador.
_Avoid_: venda parada, anomalia, encalhe (é o sinal do corpus sobre compra anterior).

**Aviso de gôndola vazia**:
Recado da vendedora ao repositor de que a gôndola de um SKU está vazia, com o setor. Fica aberto até a verificação de gôndola do SKU. Não é o aviso ao comprador: tem outro destino e fecha de outro jeito.
_Avoid_: aviso (sozinho é o recado ao comprador), pedido de reposição, chamado.

**Setor**:
Parte da loja física onde fica a gôndola de um SKU (Banho, Cama, Tapetes...). Lista cadastrada pelo admin no Copilot. O Copilot aprende o setor de cada SKU pelos avisos de gôndola vazia e pelas verificações.
_Avoid_: corredor, seção, departamento, categoria (é do catálogo).

**Verificação de gôndola**:
O que o repositor registra depois de olhar um SKU com queda de venda ou com aviso de gôndola vazia (e fecha esse aviso): `repus`, `estava_na_gondola` ou `sem_estoque_no_deposito`.
_Avoid_: conferência, inventário, contagem.

**Estoque divergente**:
Motivo de alerta de um SKU em que o repositor não achou mercadoria no depósito, mas o ERP diz que há disponível.
_Avoid_: furo de estoque, quebra.

**Participação nas vendas**:
Fração da venda de um produto que vem de um SKU dele (uma cor e um tamanho), numa janela de dias abertos. Base do mix de gôndola. Aparece também para o comprador chefe.
_Avoid_: curva, ranking, mix (sozinho).

**Capacidade da gôndola**:
Quantas peças de um produto cabem na gôndola, informadas pelo repositor e lembradas pelo Copilot.
_Avoid_: espaço, tamanho da gôndola, estoque máximo.

**Mix de gôndola**:
Quantas peças de cada SKU de um produto pôr na gôndola: a capacidade dividida pela participação nas vendas, com ao menos uma peça por SKU com estoque e sem passar do disponível. Calculado em código.
_Avoid_: sugestão (sozinho é a sugestão de pedido), planograma, grade (é a de compra).

### Usuários e notificações

**Usuário**:
Pessoa cadastrada no Copilot, com e-mail, senha e um ou mais papéis. Ver ADR-0007.
_Avoid_: conta, login, cliente (é o varejista).

**Papel**:
O que o usuário faz no Copilot e decide o que ele vê: `comprador`, `vendas`, `reposicao` ou `admin`.
_Avoid_: perfil, permissão, cargo.

**Episódio de alerta**:
Intervalo em que uma condição vale para um SKU ou para um pedido de compra (ruptura, entrega atrasada, queda de venda, estoque divergente), aberto e fechado pela varredura. Avisos e decisões sobre avisos também abrem episódios. Garante que a mesma condição notifica uma vez só.
_Avoid_: evento, incidente, ocorrência.

**Notificação**:
Um episódio de alerta visto por um usuário do papel de destino. É não lida enquanto o episódio foi aberto depois do cursor de visto do usuário. Aparece no sino e, quando é nova, num pop-up.
_Avoid_: alerta (é o que o `purchasing` calcula), aviso (é o recado da equipe de vendas), mensagem.

### Sistemas

**ERP fake**:
Banco de dados sintético que simula o ERP real do atacadista (que é o Maos, sem integração disponível). Guarda catálogo, estoque, movimentações, vendas históricas, fornecedores e pedidos de compra. Único módulo do sistema que fala com ele é `erp_adapter`.
_Avoid_: banco (é ambíguo), simulador, mock.

**Corpus**:
Conjunto de documentos sintéticos (contratos, notas de reunião, relatórios de mercado, políticas) alimentados no RAG. Fica em `corpus/`, um documento markdown por arquivo com frontmatter YAML.
_Avoid_: base de conhecimento, docs, arquivos.

**Trecho**:
Pedaço de um documento do corpus, uma seção de markdown (`##` ou `###`), com id estável no formato `<documento>#<slug-dos-titulos>`. É a unidade que o RAG indexa, busca e manda ao Jev.
_Avoid_: chunk (só em código técnico quando for o nome do algoritmo), passagem, fragmento.

**Classificação (de trecho)**:
Rótulo que o código dá a um trecho recuperado a partir das respostas do Jev: `aceito` (evidência utilizável), `conflitante` (contradiz uma premissa da pergunta) ou `descartado` (irrelevante, sem evidência ou tentando dar instrução ao modelo). Quem classifica é o código, com limiares. O Jev só responde as perguntas.
_Avoid_: filtro, score, ranking.

**Conflito entre trechos**:
Dois trechos de documentos diferentes que afirmam coisas incompatíveis sobre o mesmo fato. Ex: lead time contratado da Katrina (45 dias) contra o observado na revisão Q1/2025 (62 dias). O Copilot sinaliza o conflito e não escolhe um lado.
_Avoid_: contradição (sozinho é ambíguo com premissa da pergunta), divergência.

**Jev**:
Modelo System One da TypeSafe que toma as decisões semânticas do Copilot: intenção da pergunta, relevância de trecho do corpus, sinais qualitativos sobre fornecedor. Responde perguntas tipadas (`Choice`, `Score`, `Noul`) com confiança. Nunca faz conta, contagem ou comparação de data. Ver ADR-0002.
_Avoid_: LLM, classificador, agente.

**Redator**:
O papel do LLM no Copilot: só escreve a resposta final em linguagem natural a partir de dados já montados pelo código. Não escolhe tools nem decide nada. Ver ADR-0002.
_Avoid_: agente, chatbot, LLM com tools.

**Confiança**:
Número de 0 a 1 que o Jev devolve junto de cada resposta, derivado da distribuição de probabilidades. O código usa faixas de confiança pra decidir entre executar, pedir confirmação ou pedir esclarecimento. Nunca substitui a decisão de compra do comprador chefe.
_Avoid_: certeza, probabilidade (é outra coisa), score.

### Chat

**Intenção**:
O que o comprador chefe quer com uma pergunta do chat, uma de cinco: situação do SKU, sugestão de compra, política ou fornecedor, alertas e avisos (o painel de alertas e os avisos da equipe de vendas), fora de escopo. Quem escolhe é o Jev, com uma `Choice`; quem decide o que fazer com ela é o código.
_Avoid_: tipo de pergunta, categoria, comando.

**Entendimento (da pergunta)**:
As respostas do Jev sobre uma pergunta do chat: a intenção e o produto do catálogo citado, cada uma com probabilidades e confiança.
_Avoid_: interpretação, parse, classificação (é o nome do rótulo de trecho).

**Faixa de confiança**:
Alta, média ou baixa, conforme a confiança da intenção. Alta executa; média executa e a resposta começa confirmando o que foi entendido; baixa pede esclarecimento. Os limites são constantes nomeadas no código.
_Avoid_: nível de certeza, score.

**Esclarecimento**:
Resposta feita em código, sem redator, que devolve a pergunta ao comprador quando a intenção tem confiança baixa ou quando o SKU não foi identificado.
_Avoid_: erro, fallback.

**Registro de decisão**:
O que fica gravado de cada pergunta respondida pelo chat: a pergunta, o entendimento com as probabilidades, a faixa, a ação, os SKUs, os trechos que foram ao redator, o redator, a resposta, os sinais do corpus das sugestões e o veredito de cada citação. Serve para auditoria e para recalibrar as faixas.
_Avoid_: log (genérico demais), histórico de conversa (não há sessão).

**Citação**:
Referência `[<id do trecho>]` que o redator escreve junto de uma frase da resposta. O código extrai cada citação com a frase que a contém e dá um veredito: `confirmada` (o trecho sustenta a frase), `sem_suporte` (o trecho não trata dela), `contradita` (o trecho diz o contrário), `inventada` (o id não estava no contexto do redator, sem consultar o Jev) ou `incerta` (confiança do Jev abaixo do limiar, ou Jev não consultado). Toda citação que não é `confirmada` fica marcada no texto da resposta.
_Avoid_: referência, fonte (é o trecho, não a citação), link.
