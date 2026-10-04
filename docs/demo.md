# Roteiro de demo

Roteiro de 8 a 10 minutos que mostra o Copilot como plataforma da operação de estoque, no lugar de um vídeo. Conta a história da reunião com o comprador chefe, com três pessoas, cada uma na sua tela: o **tapete marrom** para de vender, o repositor é notificado, não acha no depósito, o comprador vê o estoque divergente e decide comprar; numa outra ponta, o comprador cobra o fornecedor de uma entrega atrasada, enquanto a vendedora consulta a previsão de chegada, avisa o repositor de uma gôndola vazia, o repositor monta a gôndola de tapetes com mais marrom que branco e a vendedora acompanha os avisos dela.

Cada passo tem a tela, o comando equivalente, o que mostrar e o que esperar. Os números saíram do ambiente local em 2026-10-04 (um domingo), com o seed recém-rodado e a política v1, e mudam com a data em que o seed roda: os dias da queda de venda são os dois últimos dias abertos antes de hoje. Vocabulário em [`CONTEXT.md`](../CONTEXT.md).

## Pré-requisitos

- Docker com `docker compose`, [`uv`](https://docs.astral.sh/uv/), `curl`, [`jq`](https://jqlang.org/) e um navegador.
- `.env` copiado do `.env.example`. A `JEV_KEY` (TypeSafe) só é necessária para o chat e os sinais do corpus ("Se sobrar tempo"); a história principal não chama o Jev.

## Preparação (antes de apresentar, uns 5 minutos)

```bash
docker compose up -d --build               # Postgres (pgvector) e o app em http://localhost:8000
uv run alembic upgrade head                # migrations até a 0023
uv run python -m scripts.seed              # ERP fake até hoje, com os cenários da demo
uv run python -m scripts.ingerir_corpus    # corpus no pgvector, só para o chat

# As quatro pessoas da demo, com a senha copilot-local (o comando lê a senha do pipe)
echo copilot-local | uv run python -m scripts.criar_admin --nome Admin --email admin@copilot.local --papeis admin
echo copilot-local | uv run python -m scripts.criar_admin --nome Carla --email carla@copilot.local --papeis comprador
echo copilot-local | uv run python -m scripts.criar_admin --nome Bia --email bia@copilot.local --papeis vendas
echo copilot-local | uv run python -m scripts.criar_admin --nome Rafa --email rafa@copilot.local --papeis reposicao
```

Para começar do zero, sem avisos, verificações, decisões e cobranças de outras apresentações, use "Resetar o ambiente local" no [README](../README.md#resetar-o-ambiente-local) (as pessoas continuam).

Deixe abertas três janelas, cada uma logada em `http://localhost:8000/ui/login.html` com uma pessoa: a **Carla** (comprador) no computador, a **Bia** (vendas) no celular e o **Rafa** (reposição) no celular ou numa janela estreita. Cada pessoa cai na tela inicial do seu papel. Use janelas anônimas ou perfis diferentes, porque a sessão fica num cookie.

Para os comandos, entre uma vez com cada pessoa no terminal:

```bash
API=http://localhost:8000
entrar() { curl -s -c "/tmp/copilot-$1" -H 'X-Requested-With: demo' -H 'Content-Type: application/json' \
  -d "{\"email\": \"$1@copilot.local\", \"senha\": \"copilot-local\"}" "$API/login" | jq -c '{nome, papeis}'; }
como() { local quem=$1; shift; curl -s -b "/tmp/copilot-$quem" -H 'X-Requested-With: demo' -H 'Content-Type: application/json' "$@"; }
for pessoa in carla bia rafa admin; do entrar $pessoa; done
```

Toda rota, menos `/health` e `/login`, exige a sessão, e todo `POST`/`PUT` exige o cabeçalho `X-Requested-With` ([ADR-0007](adr/0007-usuarios-sessao-e-papeis.md)); o `como` cuida dos dois.

## Passos

### 1. Quem usa o Copilot (30 s)

Na janela do admin (`/ui/usuarios.html`), mostre as pessoas e os papéis. Ou:

```bash
como admin "$API/usuarios" | jq -c '.[] | {nome, papeis, ativo}'
```

![Usuários e papéis, na tela do admin](img/usuarios.png)

Mostrar: o admin cadastra cada pessoa, com um ou mais papéis (comprador, vendas, reposição, admin), e redefine a senha quando alguém esquece. Ninguém digita o nome à mão: avisos, decisões, cobranças e verificações registram quem estava logado. Cada papel vê só as suas telas, e a vendedora fica logada 30 dias no celular.

### 2. O tapete marrom parou de vender (1 min)

Na janela do Rafa, o painel do repositor (`/ui/reposicao.html`) já abre com o sino aceso e o pop-up "1 SKU parou de vender com estoque". Ou:

```bash
como rafa "$API/reposicao/painel" | jq '.quedas_de_venda[] | {sku_code, cor, venda_diaria_base, ultimos_dias, venda_perdida, disponivel, setor: .setor.nome}'
como rafa "$API/notificacoes" | jq -c '.notificacoes[] | {tipo, sku_code}'
```

![Painel do repositor com o tapete marrom que parou de vender e o pop-up da notificação](img/reposicao.png)

Mostrar: o exemplo da reunião. O Tapete Banheiro marrom vendia 10,3 por dia e vendeu 5 na sexta e 0 no sábado, mas o ERP diz que há 392 no estoque: a suspeita é a gôndola, não a compra. O card diz o setor (Tapetes), a venda perdida (~16) e traz os três botões da verificação. A conta é do código: a venda dos dois últimos dias abertos contra a média dos 28 dias abertos anteriores, com os limiares da política (pergunta 11). Domingo, sem venda na loja inteira, não conta. Esperado: só o tapete marrom na lista, e o `PM-AMAR-3040-01`, que também parou de vender mas está zerado, fica com o comprador como ruptura.

### 3. O repositor não acha no depósito (30 s)

No card do tapete, escreva "Procurei no depósito todo, não achei nenhum marrom." e toque em "Não tem no depósito". Ou:

```bash
como rafa -X POST "$API/skus/TAP-MARR-4060-01/verificacoes" \
  -d '{"resultado": "sem_estoque_no_deposito", "comentario": "Procurei no depósito todo, não achei nenhum marrom."}' \
  | jq -c '{resultado, disponivel_no_erp, verificado_por}'
```

Mostrar: o card some do painel do repositor. A verificação guarda o disponível do ERP do momento (392) e quem verificou (Rafa). Se o tapete continuar parado por mais um dia aberto inteiro, ele volta.

### 4. O comprador vê o estoque divergente (1 min)

Na janela da Carla, o painel (`/ui/`) abre com o pop-up "10 SKUs entraram em ruptura, 1 estoque divergente, 1 entrega atrasou". Abra o sino. Ou:

```bash
como carla "$API/notificacoes" | jq '{nao_lidas, tipos: [.notificacoes[].tipo] | group_by(.) | map({(.[0]): length}) | add}'
como carla "$API/painel" | jq '{contagens, divergente: [.alertas[] | select(.grupo == "estoque_divergente") | {sku_code, disponivel, verificacao: .estoque_divergente | {verificado_por, comentario}}]}'
```

![Sino de notificações do comprador](img/notificacoes.png)

![Painel do comprador com o estoque divergente do tapete e as entregas atrasadas da Katrina](img/painel.png)

Mostrar: ninguém precisou avisar a Carla. As notificações nascem quando alguém abre o Copilot, uma por condição: varrer de novo não repete, e o SKU que sai e volta para a ruptura notifica outra vez. No painel, o primeiro grupo depois dos pedidos das vendedoras é "Estoque divergente": o tapete, com o recado do Rafa, "O ERP diz que tem 392 un., mas no depósito não tem". Esperado: 12 não lidas (10 rupturas, 1 estoque divergente, 1 entrega atrasada) e os contadores 1 estoque divergente, 3 entregas atrasadas e 9 em ruptura. A ruptura é a cobertura em dias abaixo do piso de alerta, 20 dias, sem lead time ([ADR-0006](adr/0006-ruptura-pela-cobertura-em-dias.md)).

### 5. A tela do SKU e a decisão de comprar (1 min)

Clique no card do tapete (`/ui/sku.html?sku=TAP-MARR-4060-01`).

![Tela do SKU do tapete marrom com a verificação do repositor e a participação nas vendas do produto](img/sku.png)

Mostrar: a situação em números grandes (392 em estoque, vende 261 por mês, segura 45 dias), a sugestão "Não comprar agora" (pelo ERP, há estoque de sobra), a verificação do Rafa à direita e, no fim, a participação nas vendas do produto: o marrom é 45% da venda do Tapete Banheiro, o branco 8%. É a mesma conta que o repositor usa para montar a gôndola, e o comprador usa para comprar a grade na proporção do que vende. Com o depósito vazio, a Carla decide comprar mesmo assim: "Vou comprar", 120 unidades, "O depósito não tem: compro já e mando contar o estoque.". Ou:

```bash
como carla -X POST "$API/skus/TAP-MARR-4060-01/decisoes" \
  -d '{"tipo": "vou_comprar", "quantidade": 120, "comentario": "O depósito não tem: compro já e mando contar o estoque."}' \
  | jq -c '{tipo, quantidade, quantidade_sugerida, decidido_por, politica_versao}'
como carla "$API/painel" | jq -c '{estoque_divergente: .contagens.estoque_divergente, decididos: [.decididos[] | {sku_code, quantidade: .decisao.quantidade}]}'
```

Esperado: a decisão guarda a quantidade decidida (120) ao lado da sugerida (0) e da versão da política, e o tapete sai do estoque divergente para "Decididos nos últimos 7 dias". O Copilot termina na decisão: o pedido sai no ERP real, depois da negociação ([ADR-0005](adr/0005-copilot-termina-na-decisao-de-compra.md)).

### 6. A entrega atrasada da Katrina e a cobrança (1 min)

Role o painel até "Entregas atrasadas". Ou:

```bash
como carla "$API/painel" | jq '.entregas_atrasadas[] | {fornecedor_nome, tem_sku_em_ruptura, pedidos: [.pedidos[] | {pedido_id, data_prevista_entrega, dias_de_atraso, skus: [.skus[].sku_code]}]}'
como carla "$API/fornecedores/014bc8ab-56dc-52d6-849d-86797abb6e59/atrasos" | jq -c '{entregas_recebidas, entregas_atrasadas, media_dias_de_atraso}'
```

Mostrar: "já comprei e não chegou" é outro problema, que se resolve cobrando o fornecedor, não comprando de novo. As entregas atrasadas vêm agrupadas por fornecedor, porque a Carla liga para a Katrina uma vez e cobra tudo: um pedido previsto para 24/09, 10 dias de atraso, com a Toalha Banho Conforto bege 70x140 em ruptura (segura 4 dias) e duas Colchas Bouti. O histórico diz que a Katrina atrasou as 2 últimas entregas, 6 dias em média. Clique em "Cobrei o fornecedor", ponha a nova previsão para daqui a 7 dias e "Liguei para a Katrina: o caminhão sai na quinta.". Ou:

```bash
NOVA=$(date -v+7d +%F 2>/dev/null || date -d '+7 days' +%F)
como carla -X POST "$API/pedidos/ad443d53-6211-57af-ace7-d5ff2da5492e/cobrancas" \
  -d "{\"nova_previsao\": \"$NOVA\", \"comentario\": \"Liguei para a Katrina: o caminhão sai na quinta.\"}" \
  | jq -c '{nova_previsao, cobrado_por}'
como carla "$API/painel" | jq -c '{contagens, entregas: [.entregas_atrasadas[].fornecedor_nome]}'
```

Esperado: o pedido sai das entregas atrasadas até a nova previsão (ou por 7 dias, sem previsão), e a toalha, que continua abaixo do piso, volta para "Em ruptura" com a sugestão de compra. Os ids do pedido e do fornecedor são fixos no seed.

### 7. A vendedora consulta a previsão e avisa o comprador (1 min)

Na janela da Bia (`/ui/aviso.html`, "Consultar e avisar"), busque "toalha banho bege 70x140" e escolha o `TBC-BEGE-70140-02`. Ou:

```bash
como bia "$API/skus?busca=toalha%20banho%20bege%2070x140" | jq -c '[.[].sku_code]'
como bia "$API/skus/TBC-BEGE-70140-02/disponibilidade" | jq -c '{disponivel, situacao, entregas}'
```

![Consulta da vendedora no celular: tem pouco, 18 no estoque, vem 24 unidades por volta de 11/10](img/consulta.png)

Mostrar: a vendedora responde o cliente no balcão sem ligar para ninguém: "Tem pouco", 18 no estoque, "Vem 24 unidades, chega por volta de 11/10", já com a nova previsão que a Carla registrou. Ela não vê preço nem fornecedor. O cliente quer 40, então ela toca em "Avisar o comprador", "Vendendo muito", "Cliente quer 40 toalhas e só chegam 24.". Ou:

```bash
como bia -X POST "$API/avisos" -d '{"sku_code": "TBC-BEGE-70140-02", "tipo": "vendendo_muito", "comentario": "Cliente quer 40 toalhas e só chegam 24."}' | jq -c '{sku_code, tipo, avisado_por}'
```

Esperado: a toalha entra no topo do painel da Carla, em "Pedidos da equipe de vendas", com o aviso da Bia, e a Carla recebe a notificação.

### 8. A vendedora vê a gôndola vazia (30 s)

Passando pelos tapetes, a Bia vê que não há nenhum cinza exposto. Ela busca "tapete cinza", escolhe o `TAP-CINZ-4060-02`, toca em "Gôndola vazia": o setor já vem como Tapetes, porque o Copilot lembra o setor de cada SKU. Comenta "Cliente procurou o cinza e não tinha nenhum exposto." e avisa o repositor. Ou:

```bash
como bia "$API/skus/TAP-CINZ-4060-02/setor" | jq -c '.setor'
como bia -X POST "$API/avisos-gondola" \
  -d '{"sku_code": "TAP-CINZ-4060-02", "setor_id": "9a41c5d0-b14f-5589-8541-3a12a9b3edcd", "comentario": "Cliente procurou o cinza e não tinha nenhum exposto."}' \
  | jq -c '{sku_code, disponivel_no_erp, avisado_por}'
```

Mostrar: a vendedora vê o problema antes de qualquer cálculo; o recado não se perde no balcão. Os setores são uma lista simples que o admin cadastra (`/ui/setores.html`).

### 9. O repositor monta a gôndola de tapetes (1 min 30 s)

Na janela do Rafa, o aviso da Bia está no topo do painel do repositor, em "Avisos das vendedoras", com a notificação. Ou:

```bash
como rafa "$API/reposicao/painel" | jq -c '.avisos_de_gondola[] | {sku_code, setor: .setor.nome, avisado_por: [.avisos[].avisado_por], disponivel, produto_id}'
```

No card, toque em "Montar a gôndola deste produto" (`/ui/gondola.html?produto=b9903f6e-8aed-5466-a9f0-7be5d46303cb`), digite 12 peças e toque em "Lembrar este número". Ou:

```bash
PRODUTO=b9903f6e-8aed-5466-a9f0-7be5d46303cb
como rafa "$API/reposicao/produtos/$PRODUTO/mix?capacidade=12" \
  | jq -c '.skus[] | {cor, participacao: (.participacao * 100 | round), disponivel, quantidade}'
como rafa -X PUT "$API/reposicao/produtos/$PRODUTO/capacidade" -d '{"capacidade": 12}' | jq -c '{capacidade}'
```

![Mix de gôndola do Tapete Banheiro: 12 peças divididas pela participação nas vendas](img/gondola.png)

Mostrar: o problema da reunião, o repositor que expõe a mesma quantidade de cada cor. Com 12 lugares, o Copilot divide pela participação nas vendas dos últimos 90 dias abertos: 4 marrons (45%), 3 cinzas (23%), 2 azuis (14%), 2 beges (10%) e 1 branco (8%). Toda cor com estoque ganha ao menos uma peça e ninguém recebe mais do que tem no depósito. A conta é do código, sem IA. O número fica lembrado para a próxima vez. Depois de montar, o Rafa registra "Repus" no aviso:

```bash
como rafa -X POST "$API/skus/TAP-CINZ-4060-02/verificacoes" \
  -d '{"resultado": "repus", "comentario": "Montei a gôndola de tapetes: 4 marrons, 3 cinzas, 2 azuis, 2 beges e 1 branco."}' \
  | jq -c '{resultado, verificado_por}'
```

Esperado: o aviso fecha e o painel do repositor fica vazio.

### 10. A vendedora acompanha os avisos dela (30 s)

Na janela da Bia, o sino acende com a resposta do Rafa. Role até "Meus avisos". Ou:

```bash
como bia "$API/notificacoes" | jq -c '.notificacoes[] | {tipo, sku_code, resultado: .detalhe.resultado}'
como bia "$API/avisos/meus" | jq -c '.[] | {para, tipo, sku_code, decisao, verificacao: .verificacao.resultado}'
```

![Meus avisos no celular da vendedora: o aviso ao comprador aguardando e a gôndola reposta](img/meus-avisos.png)

Mostrar: a vendedora sabe o que aconteceu com cada recado. O aviso ao comprador está "Aguardando o comprador" (quando a Carla decidir, a Bia é notificada com a decisão, sem o comentário, que pode ter preço) e a gôndola vazia está "Repôs a gôndola", com o comentário do Rafa.

## Se sobrar tempo

### A tela de Estoque (30 s)

Na janela da Carla, abra "Estoque" (`/ui/estoque.html`). Ou:

```bash
como carla "$API/estoque?situacao=em_ruptura&ordem=cobertura" | jq -c '{total, primeiros: [.itens[:3][] | {sku_code, disponivel, cobertura_dias}]}'
```

![Tela de Estoque com todos os SKUs, filtros e paginação](img/estoque.png)

Mostrar: todos os SKUs ativos, com busca por código, nome, cor e tamanho, filtro por categoria e situação, ordenação pelos dias que o estoque segura e paginação. O painel e o Estoque leem o ERP em lote, com um número fixo de consultas: com 5.085 SKUs (`uv run python -m scripts.seed --skus 5000`), o painel abre em cerca de 1,2 s (`uv run python -m scripts.benchmark_painel --skus 5000 --vezes 10`).

### O chat no contexto do SKU (1 min)

Na tela do SKU da toalha (`/ui/sku.html?sku=TBC-BEGE-70140-02`), clique em "Perguntar ao Copilot" e pergunte "Por que está acabando?", sem citar o produto. Ou:

```bash
como carla "$API/chat" -d '{"pergunta": "Por que está acabando?", "sku_code": "TBC-BEGE-70140-02"}' \
  | jq '{resposta, acao, faixa, intencao: .entendimento.intencao.escolha, identificacao: .identificacao | {skus, origem}, redator}'
```

Mostrar: o Jev entende a intenção, o código usa o SKU da tela (origem `contexto`) e o LLM só redige com os números que o código calculou ([ADR-0002](adr/0002-jev-decide-codigo-executa-llm-redige.md)). Esperado: `situacao_sku`, faixa média, `confirmou_e_respondeu`, em uns 5 s; a resposta repete as 18 unidades, o giro de 133 por mês e a cobertura de 4 dias "abaixo do piso de alerta da política", e lista o lead time de cada fornecedor. Ser honesto aqui: a ficha do chat não traz o pedido atrasado da Katrina, então a resposta diz que não sabe dos pedidos em andamento. Quem mostra a entrega é o painel. Para ver os sinais do corpus, pergunte "Quanto devo comprar do SKU JDCP-BRAN-CASAL-01?": a sugestão vem com o sinal de atraso da Katrina e as citações conferidas pelo Jev.

### A política de compra (1 min)

Abra "Política" (`/ui/politica.html`): cada pergunta, na linguagem do comprador, vem preenchida com o valor da versão ativa, inclusive a sensibilidade da queda de venda (pergunta 11) e o período do mix de gôndola (pergunta 12), marcadas como "a validar com o comprador".

![Política de compra](img/politica.png)

Mude uma resposta (por exemplo, a pergunta 3, de 20 para 30 dias) e salve. Esperado: a versão ativa sobe uma, e o painel, as notificações e o Estoque passam a usá-la na hora. As suposições que ainda dependem do comprador estão em [`perguntas-comprador.md`](../.scratch/sugestao-compra/perguntas-comprador.md).

## Depois da demo

Ficam gravados a verificação e os avisos, a decisão, a cobrança, a capacidade da gôndola e as notificações. O tapete fica fora do painel por 7 dias e o pedido da Katrina até a nova previsão. Para repetir a demo, use o reset do [README](../README.md#resetar-o-ambiente-local) e rode o seed de novo.

## Se algo der errado

- 401 nos comandos: a sessão do `curl` não existe ou foi revogada. Rode `entrar <pessoa>` de novo. 403: a pessoa não tem o papel da rota (a Bia não abre o painel do comprador) ou faltou o `X-Requested-With` num `POST`.
- O tapete marrom não aparece no painel do repositor: ele já tem uma verificação de outra apresentação (volta só depois de um dia aberto inteiro) ou o seed rodou num dia em que a janela não pega o 5 e o 0. Rode o reset e o seed de novo no dia da apresentação.
- O pedido da Katrina não aparece nas entregas atrasadas: ele tem uma cobrança vigente. Rode o reset.
- 503 no chat ou nos sinais: falta a `JEV_KEY` ou o Jev está fora do ar. O resto da demo não depende dele.
