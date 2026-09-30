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

**SKU**:
Unidade individual comercializável, definida por combinação de modelo, cor, tamanho e material. Ex: "Toalha Banho Conforto Bege 70x140". Um mesmo produto de catálogo pode ter dezenas de SKUs.
_Avoid_: produto (impreciso), item.

**Pedido de compra**:
Compromisso formal do atacadista com um fornecedor pra receber quantidades específicas de SKUs em uma data futura, sob condições comerciais definidas (preço, prazo de pagamento, frete).
_Avoid_: purchase order (usar em inglês só em código quando for API/DTO), ordem de compra, encomenda.

**Comprador chefe**:
Quem decide as compras no atacadista. Define a política de compra e aprova todo pedido de compra. Não é o desenvolvedor do Copilot.
_Avoid_: usuário (genérico demais), cliente (é o varejista).

**Copilot**:
A aplicação em si. Um assistente que sugere decisões de compra a partir de dados do ERP fake e do corpus de documentos, sempre com humano aprovando no fim.
_Avoid_: agente autônomo (não é autônomo por design - human-in-the-loop é premissa), assistente.

### Métricas de estoque

**Giro**:
Vendas médias de um SKU por mês, calculado como média móvel dos últimos 6 meses. Base pra todo dimensionamento de compra.
_Avoid_: rotatividade, vendas médias, saída.

**Cobertura**:
Estoque atual dividido pelo giro, expresso em meses. "SKU X tem 2.3 meses de cobertura" = com o giro atual, o estoque atende 2.3 meses.
_Avoid_: dias de estoque (é o mesmo conceito em outra unidade - escolhemos meses e ficamos com meses).

**Lead time**:
Prazo entre colocar um pedido de compra e receber a mercadoria no CD. Contratual vs observado é uma distinção que importa (ver reunião Q1/2025 no corpus).
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
Conjunto versionado de parâmetros definidos pelo comprador chefe (teto, pisos, ciclo de compra, lead time base, critério de fornecedor, sazonalidade, regra de SKU novo) que a sugestão de pedido usa. É a fonte da verdade do cálculo. O documento de política no corpus é só contexto. Ver ADR-0003.
_Avoid_: regras, configuração, estratégia.

**Teto**:
Cobertura máxima, em meses, que o SKU pode ter quando a compra chega. Parâmetro da política (R1).
_Avoid_: estoque máximo, limite.

**Piso de alerta**:
Cobertura, em dias, abaixo da qual o SKU aparece na lista de abaixo do piso. Parâmetro da política (R4).
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
Resultado determinístico de `purchasing` para um SKU: quantidade, fornecedor, memória de cálculo, alertas e versão da política usada. Quando não há compra, quantidade zero com motivo. Nunca vira pedido de compra sem aprovação do comprador chefe.
_Avoid_: recomendação, pedido sugerido, proposta.

**Sinal (do corpus)**:
O que os documentos do corpus relatam sobre o fornecedor e o produto de uma sugestão de pedido: atraso do fornecedor, venda forte do produto numa época do ano ou encalhe do produto (ou da categoria dele) numa compra anterior. O Jev responde trecho a trecho e o código transforma em sinal o que passa do limiar, com os trechos de origem. Acompanha a sugestão e nunca altera a quantidade.
_Avoid_: alerta (é o que o `purchasing` calcula a partir do ERP), insight, risco.

**Onboarding**:
Sequência de perguntas em linguagem de comprador que preenche a política de compra. Rascunho em `.scratch/sugestao-compra/perguntas-comprador.md`.
_Avoid_: setup, configuração inicial.

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
Número de 0 a 1 que o Jev devolve junto de cada resposta, derivado da distribuição de probabilidades. O código usa faixas de confiança pra decidir entre executar, pedir confirmação ou pedir esclarecimento. Nunca substitui a aprovação humana de um pedido de compra.
_Avoid_: certeza, probabilidade (é outra coisa), score.

### Chat

**Intenção**:
O que o comprador chefe quer com uma pergunta do chat, uma de quatro: situação do SKU, sugestão de compra, política ou fornecedor, fora de escopo. Quem escolhe é o Jev, com uma `Choice`; quem decide o que fazer com ela é o código.
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
O que fica gravado de cada pergunta respondida pelo chat: a pergunta, o entendimento com as probabilidades, a faixa, a ação, os SKUs, os trechos que foram ao redator, o redator e a resposta. Serve para auditoria e para recalibrar as faixas.
_Avoid_: log (genérico demais), histórico de conversa (não há sessão).

**Citação**:
Referência `[<id do trecho>]` que o redator escreve junto de uma frase da resposta. O código extrai cada citação com a frase que a contém e dá um veredito: `confirmada` (o trecho sustenta a frase), `sem_suporte` (o trecho não trata dela), `contradita` (o trecho diz o contrário), `inventada` (o id não estava no contexto do redator, sem consultar o Jev) ou `incerta` (confiança do Jev abaixo do limiar, ou Jev não consultado). Toda citação que não é `confirmada` fica marcada no texto da resposta.
_Avoid_: referência, fonte (é o trecho, não a citação), link.
