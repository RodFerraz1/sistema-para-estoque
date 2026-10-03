# Roteiro de demo

Roteiro de 5 a 8 minutos que mostra o Copilot de Compras de ponta a ponta, no lugar de um vídeo. Segue o trabalho do comprador chefe, do alerta à decisão ([ADR-0005](adr/0005-copilot-termina-na-decisao-de-compra.md)): a vendedora avisa, o comprador vê o painel, abre o SKU, pergunta no chat, olha os preços e registra a decisão. Cada passo tem a tela ou o comando, o que mostrar e o que esperar. Os números saíram do ambiente local em 2026-10-03 (seed, corpus ingerido, Jev `jev-1.13.0` e o Claude como redator), exceto onde o passo diz outra data, e mudam com a data em que o seed rodou e com a política ativa. Vocabulário em [`CONTEXT.md`](../CONTEXT.md).

## Pré-requisitos

- Docker com `docker compose`, [`uv`](https://docs.astral.sh/uv/), `curl`, [`jq`](https://jqlang.org/) e um navegador.
- `.env` copiado do `.env.example`, com a `JEV_KEY` (TypeSafe). Sem ela, o painel, os avisos e as decisões funcionam, mas a busca, os sinais do corpus e o chat respondem 503.
- A chave do redator, opcional: `ANTHROPIC_API_KEY` (Claude). Sem ela, o chat responde com os dados que reuniu, sem redação.

## Preparação (antes de apresentar, uns 5 minutos)

```bash
docker compose up -d                       # Postgres (pgvector) e o app em http://localhost:8000
uv run alembic upgrade head                # migrations até a 0012
uv run python -m scripts.seed              # ERP fake reprodutível (apaga e recria o schema erp)
uv run python -m scripts.ingerir_corpus    # corpus no pgvector (baixa o modelo de embedding na primeira vez)
```

Para começar do zero, sem avisos e decisões de outras apresentações, veja "Resetar o ambiente local" no [README](../README.md#resetar-o-ambiente-local).

Deixe abertas duas janelas: o painel (`http://localhost:8000/ui/`) no computador e a página de aviso (`http://localhost:8000/ui/aviso.html`) no celular, ou numa janela estreita do navegador.

## Passos

### 1. A vendedora avisa pelo celular (45 s)

Na página de aviso, digite "edredom bege casal", escolha o `ED-BEGE-CASAL-01` (Edredom Duplaface bege/marrom, casal), toque em "Acabou", escreva "Cliente pediu 40 peças para a semana que vem." e o nome, e envie. Ou:

```bash
curl -s "http://localhost:8000/skus?busca=edredom%20bege%20casal" | jq '[.[].sku_code]'
curl -s -X POST http://localhost:8000/avisos -H 'Content-Type: application/json' \
  -d '{"sku_code": "ED-BEGE-CASAL-01", "tipo": "acabou", "avisado_por": "Jéssica", "comentario": "Cliente pediu 40 peças para a semana que vem."}' \
  | jq '{sku_code, tipo, avisado_por}'
```

![Página de aviso no celular](img/aviso.png)

Mostrar: a página é feita para a vendedora, no celular, sem navegação nem chat. A busca não diferencia acento nem maiúscula, e o nome fica lembrado no navegador para o próximo aviso. Esperado: a busca devolve só o `ED-BEGE-CASAL-01` e a página confirma o aviso, pronta para o próximo. Hoje o comprador só fica sabendo de um produto que acabou quando alguém lembra de contar; aqui o aviso chega ao painel na hora.

### 2. O comprador vê o painel de alertas (1 min)

Atualize o painel (`/ui/`), ou:

```bash
curl -s http://localhost:8000/painel | jq '{alertas: [.alertas[] | {sku_code, motivos, avisos_abertos, quantidade_sugerida, fornecedor_sugerido}], decididos: [.decididos[].sku_code]}'
```

![Painel de alertas](img/painel.png)

Mostrar: os contadores no topo e os três grupos. O Edredom aparece em "Pedidos da equipe de vendas", com o aviso da Jéssica e o comentário, a frase "Acaba cerca de 23 dias antes de uma compra feita hoje chegar", o selo "Ruptura antes da chegada" e a sugestão de 193 unidades da Aurora Home Center. Embaixo, "Vão faltar antes da compra chegar": os SKUs que, mesmo comprando hoje, acabam antes da mercadoria chegar, o primeiro deles o `JDCP-ROSA-SOLTEIRO-10`. Esperado, com o seed recém-rodado: 9 SKUs com ruptura antes da chegada, mais os que têm aviso. O painel é calculado na hora com a política ativa (uns 2 s para os 80 SKUs do seed), não guarda estado e não chama o Jev. Os motivos de alerta são do comprador, na pergunta 10 da tela de política.

### 3. A tela do SKU (1 min)

Clique no card do Edredom (`/ui/sku.html?sku=ED-BEGE-CASAL-01`).

![Tela do SKU](img/sku.png)

Mostrar, à esquerda: a situação em números grandes (62 em estoque, nada a caminho, vende 64,3 por mês, o estoque dura 1,0 mês); a sugestão de compra, 193 unidades da Aurora por R$ 16.584,49, com os alertas (o estoque acaba antes da compra chegar, a Aurora entrega em 52 dias e não nos 40 contratados, a compra chega em época forte) e a memória de cálculo recolhida; o que os documentos dizem (sinais do corpus, que chegam por último, sem travar a tela); e as vendas dos últimos 12 meses, com o mês sem venda marcado como possível ruptura. À direita, o aviso da Jéssica e o formulário "O que você decidiu?".

A conta da sugestão é do código, com os parâmetros da política de compra ([ADR-0003](adr/0003-politica-de-compra-configuravel.md)), e o Jev só decide trecho a trecho o que os documentos relatam ([ADR-0002](adr/0002-jev-decide-codigo-executa-llm-redige.md)). Os sinais variam entre execuções: numa captura, o Jev achou demanda sazonal (76%, pela justificativa do Natal 2024); noutra, nenhum sinal.

### 4. A pergunta no chat lateral, no contexto do SKU (1 min 30 s)

Na tela do SKU, clique em "Perguntar ao Copilot" e pergunte "Por que está acabando?", sem citar o produto. Ou:

```bash
curl -s http://localhost:8000/chat -H 'Content-Type: application/json' \
  -d '{"pergunta": "Por que está acabando?", "sku_code": "ED-BEGE-CASAL-01"}' \
  | jq '{resposta, acao, faixa, intencao: .entendimento.intencao.escolha, identificacao, redator}'
```

Mostrar: o chat sabe de que produto se fala. O Jev entende a intenção, e como a pergunta não cita produto, o código usa o SKU da tela (a origem `contexto` na identificação); o LLM só redige com os números que o código calculou. Esperado: `situacao_sku`, faixa média, `confirmou_e_respondeu`, identificação `ED-BEGE-CASAL-01` com origem `contexto`, em uns 5 s. A resposta começa por "Entendi que você quer ver a situação de um SKU", repete os 62 em estoque, o giro de 64,3 por mês e a cobertura de 1,0 mês, explica que o estoque é praticamente o giro de um mês e lista o lead time observado de cada fornecedor. Abra "Como o Copilot chegou nisso" para mostrar a intenção com a confiança, a faixa, a ação e o SKU.

Para mostrar que o contexto não prende o chat, pergunte "Quanto devo comprar do SKU TBC-BEGE-70140-01?": vale o produto citado, com a sugestão, o sinal de atraso da Katrina e as citações conferidas pelo Jev (cada uma com o veredito; citação que não se confirma aparece em vermelho no texto).

### 5. Os preços para negociar com o representante (45 s)

Role a tela do SKU até "Preços para negociar", ou:

```bash
curl -s http://localhost:8000/skus/ED-BEGE-CASAL-01/precos \
  | jq '{historico: [.historico[] | {data, fornecedor_nome, preco_unitario_centavos}], precos_atuais: [.precos_atuais[] | {fornecedor_nome, preco_unitario_reais}], substitutos: [.substitutos[:3][] | {sku_code, produto_nome, preco_unitario_centavos}]}'
```

Mostrar: quando o representante quer subir o preço, o comprador tem na mesma tela o que já pagou, o preço atual de cada fornecedor e os substitutos (outro produto, mesma categoria e tamanho). Esperado: um pedido de abril de 2026 da Katrina Têxtil a R$ 85,61; preço atual de R$ 85,93 na Aurora, R$ 89,49 na Katrina e R$ 93,43 na Verdela; nove substitutos, o mais barato a Colcha Bouti off-white casal a R$ 73,23. Os preços estão em centavos na API (`preco_unitario_reais` também guarda centavos, apesar do nome).

### 6. A decisão de compra (45 s)

No formulário da tela do SKU, escolha "Vou comprar", informe 200 unidades, comente "Fechado com a Aurora a R$ 85,00.", ponha o nome e registre. Ou:

```bash
curl -s -X POST http://localhost:8000/skus/ED-BEGE-CASAL-01/decisoes -H 'Content-Type: application/json' \
  -d '{"tipo": "vou_comprar", "decidido_por": "Comprador chefe", "quantidade": 200, "comentario": "Fechado com a Aurora a R$ 85,00."}' \
  | jq '{tipo, quantidade, quantidade_sugerida, politica_versao}'
curl -s http://localhost:8000/painel | jq '{nos_alertas: [.alertas[] | select(.sku_code == "ED-BEGE-CASAL-01")] | length, decididos: [.decididos[] | {sku_code, tipo: .decisao.tipo, quantidade: .decisao.quantidade}]}'
curl -s http://localhost:8000/skus/ED-BEGE-CASAL-01/avisos | jq
```

Mostrar: o Copilot termina na decisão. Ele não cria pedido de compra: o comprador lança o pedido no ERP real (o Maos), depois de negociar com o representante. Esperado: a decisão guarda a quantidade decidida (200) ao lado da sugerida (193) e da versão da política, para comparar depois o que o Copilot sugeriu com o que o comprador fez. O Edredom sai dos alertas e vai para "Decididos nos últimos 7 dias", e o aviso da Jéssica fecha (a lista de avisos abertos fica vazia). Volta ao painel depois de 7 dias, se ainda tiver motivo, ou na hora, se a equipe de vendas avisar de novo. As outras decisões são "Estou negociando" e "Não comprar agora" (esta exige o motivo).

### 7. Se sobrar tempo: o registro de decisão do chat (45 s)

```bash
curl -s "http://localhost:8000/chat/registros?limite=2" | jq '[.[] | {pergunta, intencao, confianca, faixa, acao, skus, sku_em_contexto, redator, duracao_ms}]'
uv run python -m scripts.relatorio_registros
```

Mostrar: toda resposta do chat grava um registro de decisão para auditoria e calibração: a pergunta, o entendimento com as probabilidades, a faixa, a ação, os SKUs, o SKU em contexto, o redator, a duração, os sinais e o veredito de cada citação. O relatório resume o registro inteiro (confiança por intenção, faixas, ações, perguntas repetidas com a dispersão da confiança, vereditos e sinais); foi com ele que o M8 revisou as faixas de confiança.

### 8. Se sobrar tempo: a busca no corpus e o conflito da Katrina (1 min)

```bash
curl -s -G http://localhost:8000/rag/busca --data-urlencode "q=lead time da Katrina" \
  | jq '{classificacoes: (.trechos | group_by(.classificacao) | map({(.[0].classificacao): length}) | add), aceitos: [.trechos[] | select(.classificacao == "aceito") | .id], conflitos}'
```

Mostrar: a busca vetorial traz 30 trechos e o Jev decide trecho a trecho; o código classifica com limiares. Na execução de 2026-10-01: 8 aceitos e 22 descartados, entre os aceitos a ficha `#lead-time` (prometido 45, observado 55-65 dias), a cláusula 3 do contrato e a revisão Q1/2025 (62 dias), e um conflito entre a justificativa do Natal 2024 ("passou de 45 pra 68 dias") e as notas internas do contrato ("cumprida em setembro-outubro").

Ser honesto aqui: o conflito canônico do `CONTEXT.md`, a cláusula 3 (45 dias) contra a revisão Q1 (62 dias), **não** aparece. Os dois trechos estão aceitos, mas o Jev dá uns 0,12 ao par, abaixo do limiar de 0,40 calibrado no M8. O atraso da Katrina chega ao comprador por outro caminho: o sinal `atraso_do_fornecedor` na sugestão do `TBC-BEGE-70140-01`.

### 9. Se sobrar tempo: a política de compra (1 min)

Abra `/ui/politica.html`: cada pergunta, na linguagem do comprador, vem preenchida com o valor da versão ativa.

![Política de compra](img/politica.png)

Mude uma resposta (por exemplo, a pergunta 10, marcando "O fornecedor tem entregado depois do prazo que promete", ou a pergunta 1, de 3 para 4 meses) e salve. Depois:

```bash
curl -s http://localhost:8000/politica-compra | jq '{versao, criada_em, teto_meses: .parametros.teto_meses, motivos_de_alerta: .parametros.motivos_de_alerta}'
```

Esperado: a versão ativa sobe uma, com o valor novo, e o painel e as sugestões passam a usá-la na próxima vez que abrirem. Cada decisão de compra guarda a versão da política do momento.

## Depois da demo

O aviso e a decisão ficam gravados em `copilot.avisos` e `copilot.decisoes_compra`, e o Edredom fica fora do painel por 7 dias. Para repetir a demo, use o reset do [README](../README.md#resetar-o-ambiente-local).

## Se algo der errado

- 503 na busca, nos sinais ou no chat: falta a `JEV_KEY` ou o Jev está fora do ar. O painel, os avisos e as decisões não dependem dele, e a tela do SKU mostra os sinais como indisponíveis.
- O chat abre com "O LLM que redige a resposta está indisponível no momento": o Claude caiu (chave inválida, limite de requisições ou erro da API) e a resposta saiu sem redação. Confira a `ANTHROPIC_API_KEY` e pergunte de novo.
- O Edredom não aparece no painel: ele tem uma decisão vigente de outra apresentação. Rode o reset do README ou use outro SKU do grupo "Vão faltar antes da compra chegar".
