# Copilot de Compras

Aplicação de aprendizado de arquitetura que ajuda o atacadista de cama, mesa e banho da família a decidir compras (o que comprar, quanto, de quem e quando), usando LLM com RAG e tool use sobre dados de um ERP simulado.

## Language

### Negócio

**Atacadista**:
A empresa da família que compra de fornecedores e revende ao pequeno varejo. Segmento: cama, mesa e banho.
_Avoid_: distribuidora, revendedor (são outras figuras), atacado, "loja".

**Fornecedor**:
Empresa (normalmente fábrica ou importadora têxtil) da qual o atacadista compra produtos pra revender. Ver `.scratch/copilot-compras/rag-seeds/fornecedores/` pros fornecedores sintéticos usados.
_Avoid_: vendor, parceiro, indústria.

**SKU**:
Unidade individual comercializável, definida por combinação de modelo, cor, tamanho e material. Ex: "Toalha Banho Conforto Bege 70x140". Um mesmo produto de catálogo pode ter dezenas de SKUs.
_Avoid_: produto (impreciso), item.

**Pedido de compra**:
Compromisso formal do atacadista com um fornecedor pra receber quantidades específicas de SKUs em uma data futura, sob condições comerciais definidas (preço, prazo de pagamento, frete).
_Avoid_: purchase order (usar em inglês só em código quando for API/DTO), ordem de compra, encomenda.

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

### Sistemas

**ERP fake**:
Banco de dados sintético que simula o ERP real do atacadista (que é o Maos, sem integração disponível). Guarda catálogo, estoque, movimentações, vendas históricas, fornecedores e pedidos de compra. Único módulo do sistema que fala com ele é `erp_adapter`.
_Avoid_: banco (é ambíguo), simulador, mock.

**Corpus**:
Conjunto de documentos sintéticos (contratos, notas de reunião, relatórios de mercado, políticas) alimentados no RAG. Fica em `.scratch/copilot-compras/rag-seeds/`.
_Avoid_: base de conhecimento, docs, arquivos.
