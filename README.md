# Copilot de Compras

Assistente de decisão de compras para um atacadista de cama, mesa e banho: sugere o que comprar, quanto, de quem e quando, a partir de um ERP simulado e de um corpus de documentos (contratos, atas, políticas), sempre com o comprador chefe decidindo no fim. Vocabulário, decisões e restrições de domínio vivem em [`CONTEXT.md`](CONTEXT.md).

**MVP completo (M0-M8 do [roadmap](.scratch/copilot-compras/roadmap.md)).** A sugestão de pedido é determinística: giro, cobertura, em trânsito, lead time e MOQ calculados em código, com os parâmetros de uma política de compra que o próprio comprador preenche num onboarding. Em volta dela, a IA segue a [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md): o Jev (TypeSafe) toma decisões tipadas com confiança (intenção da pergunta, relevância de trecho, sinais do corpus como atraso do fornecedor e encalhe, verificação de citações), o código executa e um LLM (Claude) só redige a resposta do chat.

**Plataforma da operação de estoque ([spec 09](.scratch/plataforma/spec.md)).** Compra é uma cadeia que vai da necessidade do cliente da loja até a mercadoria estar na gôndola. Depois da reunião com o comprador chefe, o Copilot deixou de olhar só para ele e ganhou um painel por papel, todos alimentados pelos mesmos dados do ERP, com login e notificações:

- **Comprador chefe**: o **painel de alertas** com a ruptura pela cobertura em dias ([ADR-0006](docs/adr/0006-ruptura-pela-cobertura-em-dias.md)), o estoque divergente que o repositor achou, as entregas atrasadas agrupadas por fornecedor (com a cobrança) e os avisos da equipe de vendas; a tela de **Estoque** com busca, filtros e paginação; a **tela do SKU**, que reúne situação, vendas, sugestão de pedido, sinais do corpus, preços, entregas, verificações e a participação nas vendas, com o chat ao lado; e a **decisão de compra** (`vou_comprar`, `negociando` ou `nao_comprar_agora`), onde o Copilot termina ([ADR-0005](docs/adr/0005-copilot-termina-na-decisao-de-compra.md)).
- **Equipe de vendas**, no celular: a **consulta** (tem, tem pouco ou acabou, o que vem e quando chega), o **aviso** ao comprador, o **aviso de gôndola vazia** ao repositor e "Meus avisos", com o que cada um resolveu.
- **Repositor**: o **painel do repositor**, com os avisos de gôndola vazia e a **queda de venda** de quem tem estoque (o tapete marrom que vendia 10 por dia, vendeu 5 e depois 0), a **verificação de gôndola** e o **mix de gôndola**, que divide o espaço pela participação de cada cor nas vendas.
- **Admin**: as pessoas, os papéis ([ADR-0007](docs/adr/0007-usuarios-sessao-e-papeis.md)) e os setores da loja.

O Copilot não cria pedido de compra nem mexe no estoque: o pedido sai no ERP real do atacadista, depois da negociação. Para ver a história inteira em 8 a 10 minutos, siga o [roteiro de demo](docs/demo.md).

![Painel do comprador com o estoque divergente do tapete marrom, que o repositor não achou no depósito, e a entrega atrasada da Katrina Têxtil](docs/img/painel.png)

## Pré-requisitos

- [Docker](https://www.docker.com/) + `docker compose`
- [`uv`](https://docs.astral.sh/uv/) (gerenciador de dependências e venv)
- Python 3.12+ (o `uv` cuida do interpretador)

## Como rodar localmente

```bash
# 1. Sobe Postgres (pgvector) + app FastAPI
docker compose up -d

# 2. Aplica migrations (uma vez, ou sempre que houver nova)
uv run alembic upgrade head

# 3. Popula o ERP fake com dados sintéticos até hoje, com os cenários da demo no topo do
#    scripts/seed.py (--skus 5000 acrescenta SKUs sintéticos, para medir escala)
uv run python -m scripts.seed

# 4. Ingere o corpus em copilot.trechos_corpus (idempotente: só reprocessa documento novo ou alterado)
uv run python -m scripts.ingerir_corpus

# 5. Cria o primeiro admin (pede a senha no terminal)
uv run python -m scripts.criar_admin --nome "Seu nome" --email voce@loja.com
```

Toda tela e toda rota, menos `/health` e `/login`, exigem login ([ADR-0007](docs/adr/0007-usuarios-sessao-e-papeis.md)). O primeiro admin entra em `/ui/login.html` e cadastra as outras pessoas na tela "Usuários". Para criar alguém direto pelo terminal, passe `--papeis` (`comprador`, `vendas`, `reposicao`, `admin`, separados por vírgula); sem terminal, o comando lê a senha do pipe (`echo 'uma-senha' | uv run python -m scripts.criar_admin --nome Rafa --email rafa@loja.com --papeis reposicao`). Fora do ambiente local, defina `AMBIENTE=producao` para o cookie de sessão sair com `Secure`.

A ingestão baixa o modelo de embedding para `.cache/fastembed` na primeira vez. Os endpoints que usam o Jev (`/rag/busca`, `/chat` e `/skus/{sku_code}/sugestao-compra/sinais`) também precisam da `JEV_KEY` (chave da API da TypeSafe) no `.env`: copie o `.env.example` e preencha. Sem a chave, só esses respondem 503. A chave do redator (`ANTHROPIC_API_KEY`) é opcional: sem ela, o chat responde com os dados que reuniu, sem redação.

O app fica em `http://localhost:8000`. Confirme com:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok"}
```

A UI fica em `http://localhost:8000/ui/` (a raiz redireciona para lá). Sem sessão, a tela leva ao login, e cada pessoa cai na tela inicial do seu papel (ver "[Telas por papel](#telas-por-papel)"). Fora do Docker, suba só o banco (`docker compose up -d db`) e rode o app com `uv run uvicorn src.main:app`.

### Resetar o ambiente local

O seed (`uv run python -m scripts.seed`) apaga e recria o schema `erp` e só acrescenta, no schema `copilot`, os setores da loja e o setor conhecido dos SKUs dos cenários que faltarem. As outras tabelas do Copilot não são tocadas por ele e acumulam o que o uso grava: avisos da equipe de vendas, avisos de gôndola vazia, decisões de compra, cobranças de entrega, episódios de alerta (as notificações), verificações de gôndola, capacidades da gôndola, registros de decisão do chat e versões da política. Para voltar ao estado inicial:

```bash
docker compose exec db psql -U copilot -d copilot -c "
  TRUNCATE copilot.avisos, copilot.avisos_gondola, copilot.capacidades_gondola, copilot.setores_sku, copilot.setores, copilot.decisoes_compra, copilot.cobrancas_entrega, copilot.episodios_alerta, copilot.verificacoes_gondola, copilot.registros_decisao;
  DELETE FROM copilot.politicas_compra WHERE versao > 1;"
uv run python -m scripts.seed
```

O painel volta a ter só os motivos de alerta calculados, os registros de decisão ficam vazios e a política volta à v1 (a da migration). As pessoas cadastradas continuam. O smoke grava, desativado, o usuário "Testes automáticos" (`testes-automaticos@copilot.teste`), a quem apontam as linhas que os testes gravam; depois do reset, ele pode ser apagado com `DELETE FROM copilot.usuarios WHERE email = 'testes-automaticos@copilot.teste'`. Os trechos do corpus não precisam de reset: a ingestão é idempotente.

## Variáveis de ambiente

Todas têm padrão, menos as chaves (`JEV_KEY` e `ANTHROPIC_API_KEY`), e podem vir do `.env` na raiz (veja o `.env.example`). No `docker compose`, o app recebe o `DATABASE_URL` do próprio compose e só as duas chaves e o `REDATOR` do `.env`; as outras ficam no padrão dentro do container.

| Variável | Padrão | Para quê |
| -------- | ------ | -------- |
| `DATABASE_URL` | `postgresql+psycopg://copilot:copilot@localhost:5432/copilot` | Conexão com o Postgres. |
| `JEV_KEY` | vazio | Chave da API da TypeSafe. Sem ela, os endpoints que usam o Jev respondem 503 e os testes `externo` são pulados. |
| `JEV_MODEL` | `jev-1.13.0` | Versão fixa do Jev. Os limiares da busca e do chat foram calibrados nela. |
| `REDATOR` | `auto` | Redator das respostas do chat: `auto`, `anthropic` ou `sem_llm`. Em `auto`, o Claude se houver `ANTHROPIC_API_KEY`, senão sem LLM. `anthropic` sem a chave impede o app de subir; `sem_llm` ignora a chave. A queda do Claude vai para o redator sem LLM. |
| `ANTHROPIC_API_KEY` | vazio | Chave da API da Anthropic, para o redator Claude. Sem ela, os testes `externo_llm("anthropic")` são pulados. |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | Modelo do redator Claude. |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embedding local (fastembed, 384 dimensões). |
| `CORPUS_DIR` | `corpus` | Pasta que `scripts.ingerir_corpus` lê. |
| `FASTEMBED_CACHE_PATH` | `.cache/fastembed` | Onde o modelo de embedding fica em cache. |

## Testes

Os testes se dividem em quatro categorias:

- **Unitários e de integração leve** (padrão) - não dependem do Postgres. Usam os adapters em memória (`InMemoryERPAdapter`, `InMemoryDecisionModel`, `FakeEmbedder`).
- **Smoke end-to-end** (`tests/smoke/`) - sobem o app real contra o Postgres real com seed populado e o corpus ingerido com o embedding de verdade, e contam a história da demo com os cenários do seed: login de verdade com papel e saída (`test_login.py`); aviso e decisão de compra, ruptura com notificação, queda de venda com verificação e estoque divergente, e entrega atrasada com cobrança (`test_painel.py`); aviso de gôndola vazia com verificação e mix de gôndola (`test_reposicao.py`).
- **Externos** (marcador `externo`) - chamam o Jev real, com custo desprezível. São pulados sem `JEV_KEY`.
- **Externos com LLM** (marcador `@pytest.mark.externo_llm("anthropic")`) - chamam o Claude real e são pulados sem `ANTHROPIC_API_KEY`. O marcador sem provedor é erro de uso.

Os dois marcadores são independentes: `-m "not externo"` ainda roda os `externo_llm` cujas chaves estão no `.env`. Para rodar sem nenhuma chamada paga, exclua os dois.

```bash
# Só unitários (rápido, offline)
uv run pytest -m "not smoke and not externo and not externo_llm"

# Tudo que não chama serviço externo, smoke incluído
uv run pytest -m "not externo and not externo_llm"

# Só smoke end-to-end (requer docker compose up; aplica migrations, seed e ingestão
# do corpus sozinho, o que apaga e recria os dados do schema erp no banco local;
# avisos, decisões, cobranças, verificações e a pessoa de teste do login que o smoke
# grava são apagados no fim, e as notificações, os setores conhecidos dos SKUs e as
# capacidades da gôndola voltam ao que eram; o smoke conta com os cenários do seed
# intactos, então rode antes o reset se o banco tiver dados de uma demo)
uv run pytest tests/smoke/

# Todos os testes marcados como smoke, incluindo tests/test_seed_smoke.py
# (este exige alembic upgrade head antes)
uv run pytest -m smoke

# Tudo
uv run pytest
```

## Endpoints

Toda rota, menos `/health` e `/login`, exige a sessão do cookie `copilot_sessao` (401 sem ela) e o papel da coluna "Quem" (403 sem ele). Todo `POST`, `PUT`, `PATCH` e `DELETE` exige o cabeçalho `X-Requested-With`, contra CSRF (403 sem ele, inclusive no `/login`). Quem registra algo (aviso, decisão, cobrança, verificação, capacidade) é sempre o usuário logado: o corpo não leva nome. A vendedora não recebe preço de compra nem fornecedor em nenhuma rota que pode chamar.

| Método | Rota | Quem | O que devolve |
| ------ | ---- | ---- | ------------- |
| `GET` | `/health` | aberto | Saúde do app e do banco. |
| `POST` | `/login` | aberto | Abre a sessão (`email`, `senha`) no cookie, por 30 dias renovados a cada uso. 401 com e-mail ou senha errados, 429 com o e-mail bloqueado por tentativas. |
| `POST` | `/logout` | logado | Revoga a sessão e apaga o cookie. 204. |
| `GET` | `/eu` | logado | O usuário logado: nome, e-mail e papéis. |
| `PUT` | `/eu/senha` | logado | Troca a própria senha (`senha_atual`, `nova_senha`). 204; 422 com a senha atual errada ou a nova curta. |
| `GET` | `/usuarios` | admin | Todas as pessoas, ativas ou não, pelo nome. |
| `POST` | `/usuarios` | admin | Cadastra uma pessoa (`nome`, `email`, `senha`, `papeis`). 201; 409 com e-mail repetido; 422 nas validações. |
| `PUT` | `/usuarios/{id}/papeis` | admin | Troca os papéis. 422 sem papel ou quando o admin tira o próprio papel de admin. |
| `POST` | `/usuarios/{id}/desativar` | admin | Desativa e revoga todas as sessões da pessoa; o que ela registrou fica. 422 para a própria conta. |
| `POST` | `/usuarios/{id}/reativar` | admin | Reativa (as sessões antigas não voltam). |
| `PUT` | `/usuarios/{id}/senha` | admin | Redefine a senha de quem esqueceu. |
| `GET` | `/notificacoes` | logado | Varre as condições dos papéis do usuário (ruptura, entrega atrasada e estoque divergente para o comprador, queda de venda para o repositor) e devolve as 50 notificações mais recentes dos papéis dele e as dirigidas a ele, com o total de não lidas. |
| `POST` | `/notificacoes/vistas` | logado | Marca como lidas todas as notificações abertas até agora. 204. |
| `GET` | `/painel?busca=&categoria=&motivo=&fornecedor=` | comprador | Painel de alertas calculado na hora: `alertas` (com o `grupo` de cada SKU, na ordem de urgência), `contagens` por grupo, `entregas_atrasadas` por fornecedor, `decididos` e `skus_com_erro`. 503 com o banco fora do ar. |
| `GET` | `/estoque?busca=&categoria=&situacao=&ordem=&pagina=&por_pagina=` | comprador | Todos os SKUs ativos, paginados (50 por página, até 100): disponível, em trânsito, venda média diária, cobertura em dias e se está em ruptura. `situacao`: `em_ruptura`, `sem_venda` ou `com_transito`; `ordem`: `cobertura`, `venda_diaria` ou `nome`. |
| `GET` | `/categorias` | comprador, reposição | Categorias com algum SKU ativo. |
| `GET` | `/fornecedores` | comprador | Fornecedores que vendem algum SKU ativo, para o filtro do painel. |
| `GET` | `/fornecedores/{id}/atrasos` | comprador | Histórico de atrasos: entregas recebidas, quantas atrasaram e a média de dias de atraso. |
| `POST` | `/pedidos/{id}/cobrancas` | comprador | Cobrança de entrega do pedido inteiro (`nova_previsao` e `comentario` opcionais). Tira o pedido do painel até a nova previsão ou, sem ela, por 7 dias. 201; 404 para pedido sem entrega atrasada; 422 com a nova previsão antes de hoje. O ERP não muda. |
| `POST` | `/avisos` | vendas | Aviso ao comprador (`sku_code`, `tipo` `acabou` ou `vendendo_muito`, `comentario` opcional). Notifica o comprador. 201; 404 sem o SKU; 422 com o SKU inativo. |
| `GET` | `/avisos/meus` | vendas | Os avisos da vendedora nos últimos 30 dias, ao comprador (com a `decisao`) e ao repositor (com o `setor` e a `verificacao`), do mais recente para o mais antigo. |
| `POST` | `/avisos-gondola` | vendas | Aviso de gôndola vazia (`sku_code`, `setor_id`, `comentario` opcional). Põe o SKU no topo do painel do repositor, notifica o papel `reposicao` e lembra o setor do SKU. 201; 404 sem o SKU; 422 com SKU inativo ou setor desconhecido ou inativo. |
| `GET` | `/skus?busca=...` | comprador, vendas, reposição | Busca: até 20 SKUs ativos com todas as palavras no código, nome, cor ou tamanho, sem diferenciar acento nem maiúscula (mínimo de 2 caracteres). |
| `GET` | `/skus/{sku_code}/disponibilidade` | comprador, vendas, reposição | A consulta da vendedora: disponível, `situacao` (`tem`, `pouco` em ruptura, `acabou` com zero) e o que vem dos pedidos de compra, com a previsão de chegada (a nova previsão da última cobrança, se houver) e se está atrasada. Sem preço nem fornecedor. |
| `GET` | `/skus/{sku_code}/setor` | vendas, reposição | O setor conhecido do SKU, nulo quando ninguém disse ainda. |
| `GET` | `/skus/{sku_code}/avisos` | comprador | Avisos abertos do SKU (sem decisão de compra posterior), do mais recente para o mais antigo. |
| `GET` | `/skus/{sku_code}/decisoes` | comprador | Decisões de compra do SKU, da mais recente para a mais antiga. |
| `POST` | `/skus/{sku_code}/decisoes` | comprador | Registra a decisão de compra (`tipo`, `quantidade` em `vou_comprar`, `motivo` em `nao_comprar_agora`, `comentario` opcional), com a sugestão e a versão da política do momento, e notifica as vendedoras com aviso aberto do SKU. 201; 404 sem o SKU; 422 nas validações. Não cria pedido de compra. |
| `GET` | `/skus/{sku_code}/entregas` | comprador | O que falta chegar dos pedidos de compra abertos, com o atraso e as cobranças de cada pedido. |
| `GET` | `/skus/{sku_code}/verificacoes` | comprador, reposição | Verificações de gôndola do SKU, da mais recente para a mais antiga. |
| `POST` | `/skus/{sku_code}/verificacoes` | reposição | Verificação de gôndola (`resultado` `repus`, `estava_na_gondola` ou `sem_estoque_no_deposito`, `comentario` e `setor_id` opcionais), com o disponível do ERP do momento. Fecha os avisos de gôndola vazia do SKU e notifica cada vendedora que avisou; `sem_estoque_no_deposito` com disponível no ERP vira estoque divergente no painel do comprador. 201; 404 sem o SKU; 422 com SKU inativo ou setor inválido. |
| `GET` | `/skus/{sku_code}/precos` | comprador | Referências para negociar: preço pago em cada pedido de compra (sem os cancelados), preço atual por fornecedor e até 10 substitutos (outro produto da mesma categoria e tamanho) pelo menor preço. |
| `GET` | `/skus/{sku_code}/analise` | comprador | Análise composta: nome, produto, categoria, cor, tamanho, estoque, em trânsito, giro, cobertura (em meses e em dias), fornecedores. |
| `GET` | `/skus/abaixo-do-piso?dias=20` | comprador | SKUs com cobertura abaixo do piso de alerta. Sem `dias`, usa o `piso_alerta_dias` da política ativa. |
| `GET` | `/skus/{sku_code}/sugestao-compra` | comprador | Sugestão de pedido: quantidade, fornecedor, valor, memória de cálculo e alertas. |
| `GET` | `/skus/{sku_code}/sugestao-compra/sinais` | comprador | Sinais do corpus sobre o fornecedor e o produto da sugestão, com os trechos de origem. Lista vazia quando a sugestão não tem fornecedor; 503 sem o Jev. |
| `GET` | `/skus/{sku_code}/vendas?meses=12` | comprador | Série mensal de vendas. |
| `GET` | `/skus/{sku_code}/sazonalidade` | comprador | Multiplicadores mês-a-mês (1 = neutro). |
| `GET` | `/skus/{sku_code}/fornecedores` | comprador | Preço, MOQ e lead time por fornecedor. |
| `GET` | `/reposicao/painel?busca=&categoria=&setor=` | reposição | Painel do repositor: `avisos_de_gondola` abertos (o mais antigo primeiro, com a `queda` quando o SKU também parou de vender) e `quedas_de_venda` com estoque disponível (a maior venda perdida primeiro), cada SKU uma vez. |
| `GET` | `/reposicao/produtos?busca=` | reposição | Produtos com SKU ativo, com a capacidade da gôndola gravada. |
| `GET` | `/reposicao/produtos/{id}/mix?capacidade=` | comprador, reposição | Mix de gôndola: para cada SKU do produto, a participação nas vendas dos últimos `dias_mix_gondola` dias abertos, a venda média diária, o disponível e quantas peças pôr na gôndola. Sem `capacidade`, usa a gravada; sem nenhuma, só a participação. |
| `PUT` | `/reposicao/produtos/{id}/capacidade` | reposição | Grava quantas peças do produto cabem na gôndola (`capacidade`), no lugar da anterior. |
| `GET` | `/setores` | admin, vendas, reposição | Setores da loja, pelo nome. O admin vê todos, com quantos SKUs têm o setor como conhecido; os outros, só os ativos. |
| `POST` | `/setores` | admin | Cria um setor (`nome`). 201; 409 com nome repetido. |
| `PUT` | `/setores/{id}` | admin | Renomeia, desativa ou reativa (`nome`, `ativo`). 409 com nome repetido. |
| `GET` | `/politica-compra` | comprador | Política de compra ativa (`versao`, `criada_em`, `parametros`). |
| `PUT` | `/politica-compra` | comprador | Recebe os parâmetros completos, inclusive os motivos de alerta do painel, a sensibilidade da queda de venda e o período do mix de gôndola, valida e grava uma versão nova (201, ou 422 se inválida). |
| `GET` | `/rag/busca?q=...&k=30` | comprador | Trechos do corpus mais parecidos com a pergunta, classificados pelo filtro do Jev, e os conflitos entre eles. |
| `POST` | `/chat` | comprador | Responde em texto a pergunta do comprador chefe, com o entendimento do Jev, a faixa de confiança, a ação, os dados que foram ao redator (sugestões com os sinais do corpus) e a verificação das citações. `sku_code` opcional: o SKU da tela de onde ele pergunta (404 se não existe). |
| `GET` | `/chat/registros?limite=20` | comprador | Registros de decisão do chat, do mais recente para o mais antigo (`limite` de 1 a 100). |
| `GET` | `/ui/` | aberto | UI sem build (ver "[Telas por papel](#telas-por-papel)"). `/` redireciona para cá. |

`sku_code` é o código legível do SKU (ex.: `CB-AZUL-CASAL-05`), não o UUID.

Unidades monetárias: `preco_unitario_reais` vem em **centavos** (`7488` = R$ 74,88), enquanto `pedido_minimo_reais` vem em **reais inteiros** (`25000` = R$ 25.000). `valor_estimado_centavos` vem em centavos.

### Exemplo: `GET /skus/CB-AZUL-CASAL-05/analise`

```json
{
  "sku_code": "CB-AZUL-CASAL-05",
  "produto_nome": "Colcha Bouti",
  "categoria": "jogo_cama",
  "cor": "azul",
  "tamanho": "casal",
  "estoque": {
    "quantidade_disponivel": 90,
    "quantidade_reservada": 11,
    "atualizado_em": "2026-09-01T00:00:00Z"
  },
  "em_transito_unidades": 144,
  "giro": {
    "unidades_por_mes": 27.666666666666668,
    "meses_considerados": 6
  },
  "cobertura": {
    "meses": 3.253012048192771,
    "sem_giro": false
  },
  "fornecedores": [
    {
      "fornecedor_id": "5ad64b40-3bf9-59f0-914f-c1ac3117be68",
      "fornecedor_nome": "Verdela Home",
      "preco_unitario_reais": 7488,
      "moq_unidades": 48,
      "lead_time_dias_contratado": 60,
      "lead_time_dias_observado": 62,
      "prazo_pagamento_padrao": "28/56",
      "pedido_minimo_reais": 25000
    },
    {
      "fornecedor_id": "a8429f54-2d78-535a-a5d9-f7e8a36dbef0",
      "fornecedor_nome": "Aurora Home Center",
      "preco_unitario_reais": 8148,
      "moq_unidades": 48,
      "lead_time_dias_contratado": 40,
      "lead_time_dias_observado": 52,
      "prazo_pagamento_padrao": "30/60",
      "pedido_minimo_reais": 10000
    }
  ]
}
```

Os valores de giro e cobertura dependem da data em que o seed rodou.

### Exemplo: `GET /skus/ED-BEGE-QUEEN-02/sugestao-compra`

```json
{
  "sku_code": "ED-BEGE-QUEEN-02",
  "quantidade": 98,
  "motivo": null,
  "fornecedor": {
    "fornecedor_id": "5ad64b40-3bf9-59f0-914f-c1ac3117be68",
    "fornecedor_nome": "Verdela Home",
    "preco_unitario_reais": 9317,
    "moq_unidades": 48,
    "lead_time_dias_contratado": 60,
    "lead_time_dias_observado": 67,
    "prazo_pagamento_padrao": "28/56",
    "pedido_minimo_reais": 25000
  },
  "valor_estimado_centavos": 913066,
  "calculo": {
    "giro_mensal": 44.833333333333336,
    "disponivel": 81,
    "em_transito": 56,
    "posicao": 137,
    "lead_time_dias": 67,
    "lead_time_origem": "observado",
    "estoque_na_chegada": 36.87222222222222,
    "qtd_necessaria": 98,
    "cobertura_na_chegada_meses": 3.008302354399008
  },
  "alertas": [
    {
      "tipo": "abaixo_pedido_minimo",
      "mensagem": "O pedido de R$ 9.130,66 fica abaixo do pedido mínimo de R$ 25.000,00 do fornecedor Verdela Home. Junte com outros SKUs dele."
    },
    {
      "tipo": "lead_time_observado_acima_do_contratado",
      "mensagem": "O fornecedor Verdela Home tem entregado em 67 dias, acima dos 60 contratados."
    },
    {
      "tipo": "periodo_sazonal",
      "mensagem": "A compra chega em época forte (dezembro). Pela R2, dá pra comprar até 2,0 meses de estoque a mais, com registro em ata."
    }
  ],
  "politica_versao": 1
}
```

Como no `/analise`, os números e os alertas dependem da data em que o seed rodou. Este exemplo é de uma política com o lead time observado; com o padrão `ignorar`, `lead_time_dias` é 0 e o `lead_time_origem` é `ignorado`.

A sugestão é calculada na hora e não é gravada. Quando não há o que comprar, `quantidade` é 0 e `motivo` diz por quê (`sku_novo`, `sem_giro`, `sem_fornecedor` ou `acima_do_ponto_de_reposicao`). `calculo` fica `null` nos três primeiros motivos. `politica_versao` diz com qual versão da política a conta foi feita.

### Política de compra

O mecanismo da sugestão (contar o que está em trânsito, descontar o consumo durante o lead time quando a política o usa, respeitar o MOQ, nunca esconder violação de teto) é fixo no código. Desde a [ADR-0006](docs/adr/0006-ruptura-pela-cobertura-em-dias.md), o padrão é ignorar o lead time (`lead_time_base` `ignorar`, migration `0013`): a ruptura é a cobertura em dias abaixo do piso de alerta, e a sugestão compra o que falta para cobrir o piso de reposição mais o ciclo de compra a partir da posição de hoje. Os parâmetros de estratégia (teto, pisos, ciclo de compra, qual lead time usar, critério de fornecedor, sazonalidade, regra de SKU novo, motivos de alerta do painel) são do comprador chefe e ficam na política de compra, versionada em `copilot.politicas_compra`. Cada `PUT /politica-compra` cria uma versão nova, e a ativa é a de maior `versao`. A v1 nasce na migration com os valores da política v3 do corpus; a migration `0009` a levou ao ciclo de compra de 2 meses ("no mínimo 60 dias de cobertura de venda", pedido do dev para o MVP) e aos motivos de alerta padrão. Como piso de reposição mais ciclo fecha exatamente no teto de 3 meses, o cálculo aceita passar do teto por menos de uma unidade, que é só o arredondamento para unidade inteira.

A justificativa está em [`docs/adr/0003-politica-de-compra-configuravel.md`](docs/adr/0003-politica-de-compra-configuravel.md). Os parâmetros sem base na política v3 são chutes até o comprador responder [`.scratch/sugestao-compra/perguntas-comprador.md`](.scratch/sugestao-compra/perguntas-comprador.md). As respostas viram um `PUT /politica-compra`, sem mudança de código; a página de política da UI (`/ui/politica.html`) faz essas perguntas na linguagem do comprador, cada uma preenchida com o valor ativo, e grava a versão nova.

### Busca no corpus: `GET /rag/busca`

A busca recupera os `k` trechos mais parecidos com `q` (padrão 30, de 1 a 40) e faz ao Jev quatro perguntas sobre cada um: se é relevante para a pergunta, se tem evidência que responde a ela, se contradiz algo que a pergunta dá como certo e se tenta dar instruções ao sistema. Quem classifica é o código, com os limiares de `LIMIARES` em `src/ai/busca.py`, nesta ordem:

1. tenta dar instruções: `descartado` (`injecao`)
2. contradiz a premissa da pergunta: `conflitante`
3. não é relevante: `descartado` (`irrelevante`)
4. tem evidência: `aceito`
5. senão: `descartado` (`sem_evidencia`)

Depois, o Jev compara dois a dois os aceitos e conflitantes de documentos diferentes, entre os 6 mais parecidos. Os pares com probabilidade acima de `LIMIARES.conflito` (0,40, calibrado no M8 com 28 pares rotulados) vão para `conflitos`. A busca só sinaliza: não escolhe o lado certo nem compara datas.

A resposta traz também os `descartado`, de propósito, para auditar o filtro. Se o Jev estiver fora do ar ou faltar a `JEV_KEY`, a resposta é 503. A busca nunca sai sem o filtro. Com o corpus ainda não ingerido, a resposta é 200 com as listas vazias.

Exemplo real de `GET /rag/busca?q=lead time da Katrina` (M8, Jev real), cortado para 3 dos 30 trechos (8 aceitos e 22 descartados):

```json
{
  "pergunta": "lead time da Katrina",
  "modelo": "jev-1.13.0",
  "trechos": [
    {
      "id": "fornecedores/katrina-textil.md#lead-time",
      "documento": "fornecedores/katrina-textil.md",
      "titulo": "Katrina Têxtil S.A. > Lead time",
      "tipo": "fornecedor",
      "data": "2025-11-10",
      "tags": [
        "fornecedor-principal",
        "felpudo",
        "cama",
        "sc"
      ],
      "texto": "Katrina Têxtil S.A. > Lead time\n\n- **Prometido**: 45 dias corridos do pedido ao recebimento.\n- **Observado (média histórica)**: 55-65 dias. Ver reunião Q1/2025 que discute esse gap.",
      "similaridade": 0.7591430510098969,
      "classificacao": "aceito",
      "motivo_descarte": null,
      "avaliacao": {
        "relevante": 0.99,
        "tem_evidencia": 0.98,
        "contradiz_premissa": 0.08,
        "tenta_instruir": 0.02
      }
    },
    {
      "id": "reunioes/2024-11-natal-king-size.md#justificativa-da-excecao-a-politica",
      "documento": "reunioes/2024-11-natal-king-size.md",
      "titulo": "Reunião de compras - Natal 2024, linha King Size > Justificativa da exceção à política",
      "tipo": "reuniao",
      "data": "2024-11-18",
      "tags": [
        "natal-2024",
        "king-size",
        "katrina",
        "decisao-de-compra"
      ],
      "texto": "Reunião de compras - Natal 2024, linha King Size > Justificativa da exceção à política\n\n1. **Lead time real da Katrina em outubro-novembro passou de 45 pra 68 dias** (histórico Q3/2024). Se esperar cair pra 3 meses de estoque pra pedir, vamos furar em janeiro.\n2. **Mínimo de faturamento semestral do contrato** (R$ 240k) estava distante - segundo semestre corria abaixo do primeiro. Pedido gordo agora garante manutenção do desconto -7% em 2025.\n3. **Câmbio e algodão pressionando**: expectativa forte de reajuste acima da inflação no próximo ciclo. Estocar agora congela custo antes do repasse.\n4. **King size tem menos risco de encalhe que queen na nossa base de clientes**: giro é menor mas mais estável, sem oscilação sazonal fora do Natal.",
      "similaridade": 0.6817098633050034,
      "classificacao": "aceito",
      "motivo_descarte": null,
      "avaliacao": {
        "relevante": 0.98,
        "tem_evidencia": 0.98,
        "contradiz_premissa": 0.1,
        "tenta_instruir": 0.02
      }
    },
    {
      "id": "fornecedores/katrina-textil.md#contato-comercial",
      "documento": "fornecedores/katrina-textil.md",
      "titulo": "Katrina Têxtil S.A. > Contato comercial",
      "tipo": "fornecedor",
      "data": "2025-11-10",
      "tags": [
        "fornecedor-principal",
        "felpudo",
        "cama",
        "sc"
      ],
      "texto": "Katrina Têxtil S.A. > Contato comercial\n\nRepresentante: [placeholder] - reuniões trimestrais presenciais ou por vídeo.",
      "similaridade": 0.61969659792914,
      "classificacao": "descartado",
      "motivo_descarte": "irrelevante",
      "avaliacao": {
        "relevante": 0.11,
        "tem_evidencia": 0.04,
        "contradiz_premissa": 0.07,
        "tenta_instruir": 0.03
      }
    }
  ],
  "conflitos": [
    {
      "trecho_a": "reunioes/2024-11-natal-king-size.md#justificativa-da-excecao-a-politica",
      "trecho_b": "contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato",
      "probabilidade": 0.54
    }
  ]
}
```

O único conflito é a justificativa do Natal 2024 ("lead time real da Katrina em outubro-novembro passou de 45 pra 68 dias") contra as notas internas do contrato ("cláusula 3 é rigorosamente cumprida pela Katrina em setembro-outubro"). O par do exemplo do [`CONTEXT.md`](CONTEXT.md), a cláusula 3 do contrato (45 dias) contra a revisão Q1/2025 (62 dias observados), vem com os dois trechos aceitos, mas **não** sai como conflito: o Jev dá a ele uns 0,12, abaixo do limiar (ver os limites conhecidos do chat). O atraso da Katrina continua chegando ao comprador pelos sinais do corpus da sugestão.

`trechos` vem com os aceitos primeiro, depois os conflitantes e os descartados, e dentro de cada grupo pela similaridade. `trecho_a` é o trecho do par mais parecido com a pergunta.

O papel do Jev (ele responde, o código decide) está na [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md), e o embedding local, na [ADR-0004](docs/adr/0004-embeddings-locais.md). As perguntas, os limiares e o que o spike mediu estão em [`.scratch/rag-jev/spike-resultado.md`](.scratch/rag-jev/spike-resultado.md). O gate da ADR-0002 não passou na relevância, e o dev manteve a ADR aceitando o risco: a busca prefere deixar passar trecho irrelevante a perder trecho relevante.

### Chat: `POST /chat`

O chat segue a [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md): o Jev entende a pergunta, o código decide o que fazer e busca os dados, e o LLM só redige.

```mermaid
sequenceDiagram
    actor C as Comprador chefe
    participant A as POST /chat
    participant K as Copilot (ai)
    participant J as Jev
    participant D as catalog, ficha_sku,<br/>purchasing, politica_compra
    participant P as Postgres
    participant R as Redator (Claude)

    C->>A: pergunta
    A->>K: responder(pergunta)
    K->>J: entendimento (intenção e produto, duas Choice)
    J-->>K: probabilidades e confiança
    K->>K: faixa de confiança (alta, média ou baixa)
    alt faixa baixa, fora de escopo ou SKU não identificado
        K->>K: esclarecimento ou resposta fixa, em código
    else faixa alta ou média
        K->>K: identificação dos SKUs (código na pergunta, produto do Jev ou SKU da tela)
        K->>D: por intenção: fichas, sugestões de pedido, política ativa
        K->>P: busca vetorial no corpus (sugestão, política ou fornecedor)
        K->>J: relevância, evidência, premissa, injeção e conflitos dos trechos
        K->>J: sinais do corpus por par (fornecedor, produto) das sugestões
        K->>R: contexto montado pelo código, com todo número já calculado
        R-->>K: redação
        K->>K: limpeza da redação
        K->>J: verificação de cada citação [id do trecho]
    end
    K->>P: registro de decisão
    K-->>A: resposta, entendimento, faixa, ação, sinais e citações
    A-->>C: resposta
```

1. **Entendimento** (Jev, um request): duas `Choice` sobre a pergunta, com as probabilidades. A intenção (`situacao_sku`, `sugestao_compra`, `politica_ou_fornecedor`, `alertas_e_avisos` ou `fora_de_escopo`) e o produto do catálogo que a pergunta cita (ou `nenhum`).
2. **Faixa de confiança** da intenção (`FAIXAS` em `src/ai/chat.py`): alta (a partir de 0,80) responde; média (a partir de 0,50) responde, mas começa confirmando o que entendeu; baixa pede esclarecimento com as duas intenções mais prováveis, sem ler dados nem chamar o redator. Fora de escopo recebe uma resposta fixa.
3. **SKUs** (`src/ai/identificacao.py`): um código de SKU escrito na pergunta sempre ganha. Sem código, vale o produto escolhido pelo Jev com confiança a partir de `LIMIAR_PRODUTO` (0,60, medido com `scripts.avaliar_entendimento`), estreitado pelas cores e tamanhos citados, até 12 SKUs. Sem nenhum dos dois, vale o SKU da tela de onde o comprador perguntou (`sku_code` no corpo, origem `contexto`; ver "Chat em contexto"). Se a pergunta é sobre a situação de um SKU e nenhum foi identificado, o chat pede o código e cita os produtos candidatos.
4. **Montagem** por intenção: situação do SKU lê as fichas e a política ativa; sugestão de compra calcula as sugestões (as mesmas de `/sugestao-compra`), os sinais do corpus de cada uma, lê a política e busca no corpus; política ou fornecedor só busca no corpus; alertas e avisos lê o painel de alertas calculado na hora (avisos abertos da equipe de vendas, motivos de alerta, cobertura e sugestão), só dos SKUs citados quando a pergunta cita produto, sem usar o SKU da tela e sem buscar no corpus. Da busca, vão ao redator só os trechos `aceito` e `conflitante`, até 10, e os trechos de origem dos sinais completam esse total (os da pergunta têm prioridade).
5. **Redação**: o código renderiza o contexto (`src/ai/contexto.py`) com todo número já calculado, os sinais abaixo de cada sugestão e os trechos marcados como dado não confiável, e o redator escolhido por `REDATOR` (`ClaudeRedator` em `src/ai/claude.py`) redige seguindo `INSTRUCOES_REDATOR` (`src/ai/redator.py`): começar pelas quantidades de cada sugestão, falar de todo sinal do corpus com um trecho de origem, copiar os números sem converter nem comparar, não recomendar fornecedor nem opinar sobre a compra, citar só ids de trecho, um por frase, e nunca aprovar pedido. A redação passa por uma limpeza em código (`limpar_redacao`: hífen não separável vira hífen, espaços especiais viram espaço, `【】` vira `[]` e o espaço de largura zero sai), para o código do SKU ser copiável e as citações serem extraídas. Sem a chave da Anthropic, ou se o Claude falhar, o `RedatorSemLLM` devolve o contexto sem redação e `redator` vira `sem_llm`.
6. **Verificação das citações** (só quando um LLM redigiu): cada `[id do trecho]` da redação é conferido pelo Jev contra a frase que o cita, e o que não é confirmado fica marcado no texto. Detalhes na seção seguinte.

`acao` diz o que o chat fez: `respondeu`, `confirmou_e_respondeu`, `pediu_esclarecimento` ou `fora_de_escopo`. `redator` é nulo nas respostas feitas em código. Sem `JEV_KEY`, ou com o Jev fora do ar no entendimento, a resposta é 503. Cada pergunta é independente: não há histórico de conversa.

Exemplo real de `POST /chat` (do M5, antes dos campos `citacoes` e `sugestoes[].sinais`, que estão no exemplo da seção seguinte) com `{"pergunta": "Qual a situação do SKU TBC-BEGE-70140-01?"}`, com as probabilidades do produto cortadas para as que não são zero (o Jev devolve uma por produto do catálogo):

```json
{
  "resposta": "**Situação do SKU TBC‑BEGE‑70140‑01**\n\n- **Estoque:** 180 unidades  \n- **Giro:** 142 unidades/mês (média de 6 meses)  \n- **Cobertura atual:** 1,3 meses [SKU/TBC-BEGE-70140-01]  \n\n**Conformidade com a política de compra ativa (v1):**  \n- Teto de cobertura: 3,0 meses  \n- Piso de reposição (quando a compra chega): 1,0 meses  \n- Piso de alerta: 20 dias (≈0,66 meses)  \n\nA cobertura de 1,3 meses está **acima do piso de reposição** e **abaixo do teto**, portanto a situação está dentro dos limites aceitáveis e não há alerta.\n\n**Fornecedor recomendado (menor preço):** Katrina Têxtil – R$ 17,06/un [SKU/TBC-BEGE-70140-01]  \n- MOQ: 36 unidades  \n- Lead time observado: 33 dias (contratado 35 dias)  \n\nSe houver necessidade de reposição, a compra pode ser feita com a Katrina Têxtil, respeitando o MOQ de 36 unidades.",
  "acao": "respondeu",
  "faixa": "alta",
  "entendimento": {
    "intencao": {
      "escolha": "situacao_sku",
      "confianca": 1.0,
      "probabilidades": {
        "fora_de_escopo": 0.0,
        "sugestao_compra": 0.0,
        "situacao_sku": 1.0,
        "politica_ou_fornecedor": 0.0
      }
    },
    "produto": {
      "escolha": "Toalha Banho Conforto",
      "confianca": 0.99,
      "probabilidades": {
        "Toalha Banho Conforto": 0.99,
        "nenhum": 0.01
      }
    },
    "modelo": "jev-1.13.0"
  },
  "identificacao": {
    "skus": [
      "TBC-BEGE-70140-01"
    ],
    "total_skus": 1,
    "origem": "codigo",
    "produto": null,
    "candidatos": []
  },
  "fichas": [
    {
      "sku_code": "TBC-BEGE-70140-01",
      "produto_nome": "Toalha Banho Conforto",
      "categoria": "felpudo",
      "estoque": {
        "quantidade_disponivel": 180,
        "quantidade_reservada": 22,
        "atualizado_em": "2026-09-01T00:00:00Z"
      },
      "giro": {
        "unidades_por_mes": 142.0,
        "meses_considerados": 6
      },
      "cobertura": {
        "meses": 1.267605633802817,
        "sem_giro": false
      },
      "fornecedores": [
        {
          "fornecedor_id": "014bc8ab-56dc-52d6-849d-86797abb6e59",
          "fornecedor_nome": "Katrina Têxtil",
          "preco_unitario_reais": 1706,
          "moq_unidades": 36,
          "lead_time_dias_contratado": 35,
          "lead_time_dias_observado": 33,
          "prazo_pagamento_padrao": "30/60/90",
          "pedido_minimo_reais": 12000
        },
        {
          "fornecedor_id": "a8429f54-2d78-535a-a5d9-f7e8a36dbef0",
          "fornecedor_nome": "Aurora Home Center",
          "preco_unitario_reais": 2017,
          "moq_unidades": 120,
          "lead_time_dias_contratado": 40,
          "lead_time_dias_observado": 37,
          "prazo_pagamento_padrao": "30/60",
          "pedido_minimo_reais": 10000
        }
      ]
    }
  ],
  "sugestoes": [],
  "trechos": [],
  "conflitos": [],
  "redator": "groq:openai/gpt-oss-120b",
  "registro_id": "bef7f26c-3cff-409a-9f89-eb6176a1f6da"
}
```

A redação desse exemplo, do M5, mostra os limites que o M8 atacou (ver os limites conhecidos do chat): ela compara a cobertura com o teto e os pisos, converte o piso de dias em meses, recomenda um fornecedor e inventa a citação `[SKU/...]`. Os números da ficha, da política e dos fornecedores vêm do ERP e estão certos.

### Registro de decisão: `GET /chat/registros`

Todo `POST /chat` respondido grava um registro em `copilot.registros_decisao` (migrations [`0004_registros_decisao`](alembic/versions/0004_registros_decisao.py) e [`0005_sinais_e_citacoes`](alembic/versions/0005_sinais_e_citacoes.py)): a pergunta, o entendimento cru do Jev com as probabilidades, a faixa, a ação, os SKUs, os ids dos trechos que foram ao redator, o redator, a resposta, a duração, os sinais de cada sugestão (`sinais`, um item por SKU sugerido, com `sinais` vazio quando foram calculados sem nenhum sinal e nulo quando o Jev caiu e eles não foram calculados) e a verificação de cada citação (`citacoes`). Se a gravação falhar, a resposta falha junto, porque o registro é requisito de auditoria. Com o Jev fora do ar não há registro, porque nada foi decidido. Foi com esses registros que o M8 revisou as faixas e o limiar do produto: `uv run python -m scripts.relatorio_registros` resume o registro (confiança por intenção, faixas, ações, redator, durações, vereditos e sinais) e `--exportar ARQ` grava as perguntas para rotular às cegas. O endpoint não chama o Jev.

Exemplo de `GET /chat/registros?limite=1` logo depois do `POST /chat` acima (também do M5, sem `sinais` e `citacoes`, que agora vêm como listas), com o mesmo corte nas probabilidades:

```json
[
  {
    "id": "bef7f26c-3cff-409a-9f89-eb6176a1f6da",
    "criado_em": "2026-09-30T19:15:58.201829Z",
    "pergunta": "Qual a situação do SKU TBC-BEGE-70140-01?",
    "intencao": "situacao_sku",
    "confianca": 1.0,
    "faixa": "alta",
    "acao": "respondeu",
    "skus": [
      "TBC-BEGE-70140-01"
    ],
    "entendimento": {
      "intencao": {
        "escolha": "situacao_sku",
        "confianca": 1.0,
        "probabilidades": {
          "situacao_sku": 1.0,
          "fora_de_escopo": 0.0,
          "sugestao_compra": 0.0,
          "politica_ou_fornecedor": 0.0
        }
      },
      "produto": {
        "escolha": "Toalha Banho Conforto",
        "confianca": 0.99,
        "probabilidades": {
          "Toalha Banho Conforto": 0.99,
          "nenhum": 0.01
        }
      },
      "modelo": "jev-1.13.0"
    },
    "trechos": [],
    "redator": "groq:openai/gpt-oss-120b",
    "resposta": "**Situação do SKU TBC‑BEGE‑70140‑01**\n\n- **Estoque:** 180 unidades  \n- **Giro:** 142 unidades/mês (média de 6 meses)  \n- **Cobertura atual:** 1,3 meses [SKU/TBC-BEGE-70140-01]  \n\n**Conformidade com a política de compra ativa (v1):**  \n- Teto de cobertura: 3,0 meses  \n- Piso de reposição (quando a compra chega): 1,0 meses  \n- Piso de alerta: 20 dias (≈0,66 meses)  \n\nA cobertura de 1,3 meses está **acima do piso de reposição** e **abaixo do teto**, portanto a situação está dentro dos limites aceitáveis e não há alerta.\n\n**Fornecedor recomendado (menor preço):** Katrina Têxtil – R$ 17,06/un [SKU/TBC-BEGE-70140-01]  \n- MOQ: 36 unidades  \n- Lead time observado: 33 dias (contratado 35 dias)  \n\nSe houver necessidade de reposição, a compra pode ser feita com a Katrina Têxtil, respeitando o MOQ de 36 unidades.",
    "duracao_ms": 3676
  }
]
```

### Sinais do corpus e citações verificadas

Os dois seguem a [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md): o Jev responde perguntas estreitas e o código decide com limiares medidos contra o Jev real.

**Sinais do corpus** (`src/ai/sinais.py`). Para o par (fornecedor sugerido, produto) de uma sugestão de pedido, o código faz uma busca focada no corpus ("<fornecedor> e <produto>: atrasos de entrega, vendas por época do ano e estoque encalhado", 15 trechos, sem conflitos), manda os até 10 trechos `aceito` e `conflitante` ao Jev e pergunta, trecho a trecho, se ele relata atraso desse fornecedor, venda forte do produto (ou da categoria) numa época do ano e encalhe do produto (ou da categoria) numa compra anterior. Cada tipo com algum trecho acima de `LIMIARES_SINAIS` (atraso 0,80, venda por época 0,75, encalhe 0,55, pela regra de calibração do M8 sobre as respostas medidas com `scripts.avaliar_sinais`) vira um sinal com a mensagem feita em código, os ids dos trechos de origem e a maior probabilidade. Sugestão sem fornecedor (quantidade zero) não tem sinal. Os sinais acompanham a sugestão e **nunca alteram a quantidade**. No chat, são calculados uma vez por par (fornecedor, produto), e não por SKU.

`GET /skus/TBC-BEGE-70140-01/sugestao-compra/sinais` (Jev real, banco do seed, no M6; com o limiar de atraso de 0,80 do M8, a justificativa do Natal 2024, com 0,86, entra como terceiro trecho de origem):

```json
[
  {
    "tipo": "atraso_do_fornecedor",
    "mensagem": "Os documentos relatam atraso de entrega da Katrina Têxtil.",
    "trechos": [
      "fornecedores/katrina-textil.md#lead-time",
      "reunioes/2025-q1-revisao-fornecedores.md#riscos-consolidados-de-fornecimento"
    ],
    "probabilidade": 0.96
  }
]
```

**Citações verificadas** (`src/ai/citacoes.py`). Depois que um LLM redige (a resposta do `RedatorSemLLM`, o esclarecimento e o fora de escopo não passam por aqui), o código extrai cada `[id do trecho]` com a frase que o contém. Id que não estava no contexto do redator é `inventada`, sem chamar o Jev. Os demais vão ao Jev com uma `Choice` (o trecho sustenta, contradiz ou não trata da frase), e o código decide: confiança abaixo de `LIMIAR_CITACAO` (0,80, pela regra de calibração do M8 sobre as respostas medidas com `scripts.avaliar_citacoes`; com 0,50, três trechos de outro fornecedor saíam como "diz o contrário") é `incerta`; senão `confirmada`, `contradita` ou `sem_suporte`. Toda citação que não é `confirmada` fica marcada no texto, mantendo o id: `[<id> - não confirmada]` (`sem_suporte` e `incerta`), `[<id> - o trecho diz o contrário]` e `[<id> - trecho inexistente]`. O texto só é marcado, nunca reescrito.

Só conta como citação o colchete com formato de id de trecho (`<caminho>.md#<slug>`). Colchetes como `[SKU/TBC-BEGE-70140-01]`, `[JDCP-BRAN-QUEEN-02]` e `[Política de compra ativa (v1)]` ficariam sem marca. O redator os escrevia até o M7 (15 na rodada de base do M8); com as instruções do M8, nenhum nas rodadas medidas.

**Queda do Jev** nos sinais ou na verificação não derruba o chat, porque a pergunta já foi entendida. Nos sinais, que são calculados antes da redação, as sugestões saem com `sinais` nulo e o contexto do redator ganha a observação "Não foi possível calcular os sinais do corpus agora (o modelo de decisão está indisponível), então as sugestões vêm sem eles.". Na verificação, que roda depois da redação, as citações do contexto ficam `incerta` (marcadas como não confirmadas) e o código acrescenta ao fim da resposta "Observação: não consegui verificar as citações agora, então elas vêm marcadas como não confirmadas."

Exemplo real de `POST /chat` com `{"pergunta": "Quanto devo comprar do TBC-BEGE-70140-01?"}` (Jev e Groq reais, 8,1 s; a Groq foi o redator até o M8 e saiu depois), sem `entendimento` (`sugestao_compra` com 0,95), `identificacao`, `trechos`, `conflitos` e `registro_id`, e com a `sugestao` reduzida a `sku_code` e `quantidade` (o resto é igual ao de `/sugestao-compra`):

```json
{
  "resposta": "A quantidade sugerida para o SKU TBC‑BEGE‑70140‑01 é **261 unidades** (valor estimado R$ 4.452,66). Entretanto, esse valor está **abaixo do pedido mínimo de R$ 12.000,00** exigido pela Katrina Têxtil, sendo necessário combinar a compra com outros SKUs do mesmo fornecedor. Observe ainda que o lead‑time observado da Katrina está entre 55‑65 dias ([fornecedores/katrina-textil.md#lead-time - não confirmada]) e que há risco de dependência alta desse fornecedor ([reunioes/2025-q1-revisao-fornecedores.md#riscos-consolidados-de-fornecimento - não confirmada]).",
  "acao": "respondeu",
  "faixa": "alta",
  "sugestoes": [
    {
      "sugestao": {
        "sku_code": "TBC-BEGE-70140-01",
        "quantidade": 261
      },
      "sinais": [
        {
          "tipo": "atraso_do_fornecedor",
          "mensagem": "Os documentos relatam atraso de entrega da Katrina Têxtil.",
          "trechos": [
            "fornecedores/katrina-textil.md#lead-time",
            "reunioes/2025-q1-revisao-fornecedores.md#riscos-consolidados-de-fornecimento"
          ],
          "probabilidade": 0.96
        }
      ]
    }
  ],
  "citacoes": [
    {
      "trecho_id": "fornecedores/katrina-textil.md#lead-time",
      "afirmacao": "Observe ainda que o lead-time observado da Katrina está entre 55-65 dias e que há risco de dependência alta desse fornecedor.",
      "veredito": "incerta",
      "confianca": 0.42
    },
    {
      "trecho_id": "reunioes/2025-q1-revisao-fornecedores.md#riscos-consolidados-de-fornecimento",
      "afirmacao": "Observe ainda que o lead-time observado da Katrina está entre 55-65 dias e que há risco de dependência alta desse fornecedor.",
      "veredito": "incerta",
      "confianca": 0.27
    }
  ],
  "redator": "groq:openai/gpt-oss-120b"
}
```

Os sinais saem abaixo da sugestão no contexto do redator, com os ids de origem, e os trechos de origem entram na seção de trechos depois dos da pergunta, até o total de 10. Aqui (M6, instruções antigas) a redação usou o sinal de atraso, mas pôs as duas citações numa frase só, que junta o lead time e a dependência do fornecedor, e o Jev não confirmou nenhum dos dois trechos para a frase inteira (0,42 e 0,27). Os mesmos `sinais` e `citacoes` ficam no registro de decisão.

A mesma pergunta no fim do M8, com as instruções novas e o redator Claude (passo 4 do [roteiro de demo](docs/demo.md)), começa pelas 213 unidades da Katrina, "o fornecedor escolhido pela política", repete a memória de cálculo e os alertas, fala do sinal de atraso com um trecho por frase (a ficha `#lead-time`, a revisão Q1 e a justificativa do Natal, que entrou no sinal com o limiar novo de 0,80) e as três citações saem `confirmada` com 1,00.

### Limites conhecidos do chat

Cada milestone do chat foi fechado rodando as perguntas de `evals/casos.json` (20 casos) e de `evals/casos_redator.json` (4 perguntas de sugestão e situação por código, que exercitam os sinais) pelo chat inteiro, com o Jev e o redator reais. Cada pergunta grava um registro de decisão:

```bash
uv run python -m scripts.rodar_casos_chat --respostas --pausa 60
uv run python -m scripts.rodar_casos_chat --respostas --pausa 60 --casos evals/casos_redator.json
```

O script conta, por caso e no total, o que dá para medir sem ler a resposta: colchetes sem id de trecho, sinais do corpus com algum trecho de origem citado e sugestões com a quantidade escrita no texto. Os resultados estão nos comentários dos tickets de fechamento: M5 em [`.scratch/chat/issues/05-readme-e-smoke.md`](.scratch/chat/issues/05-readme-e-smoke.md), M6 em [`.scratch/sinais-e-citacoes/issues/03-chat-com-sinais-e-citacoes.md`](.scratch/sinais-e-citacoes/issues/03-chat-com-sinais-e-citacoes.md) e M8 em [`.scratch/refinamentos/issues/02-prompt-do-redator.md`](.scratch/refinamentos/issues/02-prompt-do-redator.md) (antes e depois do prompt) e [`06-readme-screenshots-e-demo.md`](.scratch/refinamentos/issues/06-readme-screenshots-e-demo.md) (rodada final).

**O que o M8 resolveu:**

- **Instruções do redator.** Com o prompt novo e a limpeza em código, na Groq: colchetes sem id de trecho de 15 para 0, sinais citados de 1/3 para 3/3 e quantidades no texto de 2/5 para 5/5; nenhuma conversão de unidade, nenhuma recomendação de fornecedor e nenhum hífen não separável nas rodadas depois da mudança. O exemplo do M5 acima comparava, convertia, recomendava e citava `[SKU/...]`; a mesma pergunta na rodada final responde só com os números da ficha e lista os fornecedores sem escolher nenhum.
- **Pergunta limítrofe.** "Qual o lead time de verdade da Katrina?" saía `situacao_sku` com confiança de 0,31 a 0,49 e pedia esclarecimento. Com critérios estruturados na `Choice` da intenção, sai `politica_ou_fornecedor` com 0,98 a 0,99 e é respondida. Intenção de 44/45 para 45/45 nas perguntas rotuladas (`evals/casos.json` e `evals/intencoes.json`), 20/20 e 4/4 na rodada final.
- **Limiares calibrados por uma regra única** (`scripts/calibracao.py`), que não escolhe o extremo quando a amostra não tem erro e mantém o limiar quando a amostra não basta: sinais de atraso 0,90 para 0,80, venda por época 0,80 para 0,75, encalhe 0,60 para 0,55; citação 0,50 para 0,80 (com 0,50, três trechos de outro fornecedor saíam como "diz o contrário"); conflito 0,10 para 0,40.
- **Conflitos inundando a resposta.** Com 0,10, as buscas das 10 perguntas do corpus sinalizavam 25 conflitos, a maioria regra contra exceção registrada ou fatos diferentes. Com a pergunta reescrita e 0,40, sinalizam 5, todos conflitos reais.
- **Redator Claude.** O `ClaudeRedator` (Sonnet 5.5, esforço baixo) substituiu a Groq gratuita, que derrubava perguntas seguidas por limite de tokens e foi removida depois do M8. `REDATOR` troca entre Claude e sem LLM sem mexer em código. Na medição com o Sonnet, nenhuma queda do redator e nenhum colchete sem id de trecho: em `casos_redator.json`, intenção 4/4, sinais citados 3/3, quantidades no texto 3/3 e citações com 5 `confirmada` e 1 `incerta`; em `casos.json`, intenção 20/20, quantidades 2/2 e 56 `confirmada` e 1 `incerta`. Nenhuma citação saiu `inventada` ("trecho inexistente"), que era o que a Groq fazia ao copiar o exemplo das instruções sem trecho no contexto.

**O que continua:**

- **Conflito canônico perdido.** O limiar de 0,40 não deixa passar nenhum falso conflito, mas perde 4 dos 7 conflitos rotulados, inclusive o exemplo do `CONTEXT.md`: a cláusula 3 do contrato da Katrina (45 dias) contra a revisão Q1/2025 (62 dias observados) fica em 0,12. O Jev só passa do limiar quando um trecho afirma que o prazo é cumprido; o contrato contra o observado parece ser lido como promessa, e não como fato. Os dois trechos continuam indo ao redator, e o atraso da Katrina continua aparecendo pelo sinal de atraso da sugestão; só a seção de conflitos não os liga.
- **Citações de sinais de encalhe não se confirmam.** A mensagem do sinal generaliza para a categoria ("encalhe de Colcha Bouti ou da categoria dele numa compra anterior") e o trecho fala do jogo Veraneio, então o Jev não confirma a frase e a citação sai "não confirmada" em todas as rodadas. É da mensagem do sinal, não do prompt.
- **O redator ainda escorrega em contas e citações.** Na rodada final, com a Groq: o c06 diz que 2,3 meses ficam "dentro do teto de 3 meses" e põe trechos da reunião do Natal em frases da sugestão, que a verificação marca como "o trecho diz o contrário"; e, nas perguntas de situação de SKU, que não têm trecho no contexto, o redator cita a ficha com o formato do exemplo das instruções (`[pasta/fichas.md#tbc-bege-70140-01]`), que a verificação marca como "trecho inexistente" (8 no c01 e 4 no p04). Com o Sonnet, a citação da ficha não se repetiu; as conclusões próprias do c06 não foram conferidas, porque as contagens não leem o texto. O texto só é marcado, nunca reescrito.
- **Alarme falso na verificação.** A afirmação é a frase inteira: frase com uma conclusão do redator sai `incerta` mesmo com o trecho certo. Com o limiar de citação em 0,80, há mais "não confirmada" do que antes (2 `incerta` em 26 citações dos casos na rodada final).
- **Faixa média quase some, e as faixas não foram recalibradas.** Com os critérios novos, 44 das 45 perguntas rotuladas saem com confiança alta e nenhuma intenção sai errada, então a regra não tem negativos: as faixas (0,80 e 0,50) e o `LIMIAR_PRODUTO` (0,60) ficam por amostra insuficiente. Não há como saber se uma intenção errada também viria com confiança alta.
- **Poucos SKUs identificados pelo nome.** Quando o Jev escolhe o produto com confiança abaixo de 0,60, ou não acha o produto (a toalha de rosto 45x70 não existe no catálogo), a pergunta de situação pede o código do SKU e a de sugestão de compra responde só com o corpus e a política, sem quantidade. Na rodada final, 3 das 5 perguntas de situação pediram o código e 4 das 5 de sugestão ficaram sem SKU.

### Fluxo do comprador: painel, aviso e decisão de compra

O Copilot segue o trabalho do comprador chefe, do alerta à decisão ([ADR-0005](docs/adr/0005-copilot-termina-na-decisao-de-compra.md)). O módulo `painel` é dono dos avisos da equipe de vendas (`copilot.avisos`, migration [`0010_avisos`](alembic/versions/0010_avisos.py)), das decisões de compra (`copilot.decisoes_compra`, migration [`0011_decisoes_compra`](alembic/versions/0011_decisoes_compra.py)), das cobranças de entrega (`copilot.cobrancas_entrega`, migration [`0017_entregas_atrasadas`](alembic/versions/0017_entregas_atrasadas.py)) e da composição do painel de alertas, da tela de Estoque e da consulta da vendedora. O Copilot não escreve no ERP: o pedido de compra sai no ERP real, depois da negociação com o representante.

```mermaid
sequenceDiagram
    actor V as Equipe de vendas
    actor C as Comprador chefe
    participant A as API
    participant M as painel
    participant U as purchasing
    participant P as Postgres

    V->>A: POST /avisos (acabou ou vendendo muito)
    A->>M: registrar_aviso
    M->>P: copilot.avisos
    C->>A: GET /painel
    A->>M: painel
    M->>U: sugerir_pedidos(retrato do ERP em lote, determinístico, sem Jev)
    M-->>C: alertas por grupo, entregas atrasadas por fornecedor e decididos
    C->>A: tela do SKU: análise, sugestão, sinais, preços, vendas, avisos e decisões
    C->>A: POST /chat com o sku_code da tela
    C->>A: POST /skus/{sku}/decisoes (vou_comprar, negociando ou nao_comprar_agora)
    A->>M: registrar_decisao
    M->>U: sugestão do momento (quantidade e versão da política)
    M->>P: copilot.decisoes_compra
```

**Painel de alertas** (`GET /painel`, a tela inicial do comprador). Calculado na hora, sem estado próprio, com a política ativa, sobre um retrato do ERP lido em lote (`FichaSKU.retrato()`: estoques, giros, vendas diárias, fornecedores e itens em trânsito de todos os SKUs ativos, uma consulta cada). Os **motivos de alerta** de um SKU são os alertas da sugestão que estão nos `motivos_de_alerta` da política, mais `abaixo_do_piso_alerta` (a **ruptura**: cobertura em dias abaixo do `piso_alerta_dias`), `entrega_atrasada` (pedido de compra com a data prevista vencida e sem cobrança vigente) e `estoque_divergente` (o repositor não achou no depósito o que o ERP diz que tem). Os três são o padrão; o comprador muda na pergunta 10 da tela de política. O SKU entra no painel se tem aviso aberto ou algum motivo, num grupo, nesta ordem: pedidos da equipe de vendas, estoque divergente, entregas atrasadas, em ruptura, vão faltar antes da compra chegar (só com o lead time ligado) e outros alertas. Em cada grupo, o disponível zero vem primeiro, depois a menor cobertura em dias. `entregas_atrasadas` traz os mesmos pedidos agrupados por fornecedor, o fornecedor com SKU em ruptura primeiro, para o comprador ligar uma vez e cobrar tudo. `parou_de_vender` marca o SKU em queda de venda sem estoque. A busca e os filtros (`busca`, `categoria`, `motivo`, `fornecedor`) filtram o mesmo retrato. Um SKU sem a linha de estoque no ERP vai para `skus_com_erro` em vez de derrubar o painel. O painel faz 13 consultas fixas, conferidas por um listener do SQLAlchemy em `src/api/tests/test_painel_em_escala.py`: com o seed (85 SKUs) responde em uns 0,05 s e traz 10 SKUs em ruptura, um deles com entrega atrasada; com 5.085 SKUs (`scripts.seed --skus 5000`), a mediana do `scripts.benchmark_painel` foi 1,22 s. O painel não chama o Jev.

```json
{
  "sku_code": "PM-AMAR-3040-01",
  "produto_nome": "Pano Multiuso",
  "cor": "amarelo",
  "tamanho": "30x40",
  "disponivel": 0,
  "cobertura_atual_meses": 0.0,
  "cobertura_atual_dias": 0.0,
  "cobertura_na_chegada_sem_compra_meses": 0.0,
  "cobertura_na_chegada_sem_compra_dias": 0.0,
  "motivos": ["abaixo_do_piso_alerta"],
  "quantidade_sugerida": 291,
  "fornecedor_sugerido": "Malha Fina",
  "avisos_abertos": 0,
  "ultimo_aviso": null,
  "so_por_aviso": false,
  "grupo": "em_ruptura",
  "parou_de_vender": true,
  "estoque_divergente": null
}
```

**Aviso da equipe de vendas** (`POST /avisos`, tela "Consultar e avisar"). A vendedora busca o SKU pelo nome, cor ou tamanho (`GET /skus?busca=`, sem diferenciar acento nem maiúscula), vê a disponibilidade, marca `acabou` ou `vendendo_muito`, escreve um comentário se quiser e envia, em nome dela. O SKU entra no painel na hora, no primeiro grupo, mesmo quando o cálculo não vê problema (`so_por_aviso`), porque a loja pode estar vendo algo que o histórico não mostra. SKU inativo não aceita aviso (422).

**Decisão de compra** (`POST /skus/{sku}/decisoes`, na tela do SKU). `vou_comprar` exige a quantidade (maior que zero), `nao_comprar_agora` exige o motivo, e `negociando` só tira o SKU do painel enquanto o comprador conversa com o representante. A decisão guarda a quantidade sugerida e a versão da política do momento, para comparar depois o que o Copilot sugeriu com o que o comprador decidiu. Nada é atualizado: **aviso aberto** é o que não tem decisão do mesmo SKU depois dele, e **decisão vigente** é a mais recente do SKU, com menos de 7 dias (`PRAZO_DA_DECISAO`) e sem aviso posterior. Com decisão vigente, o SKU sai dos alertas e vai para `decididos`; volta quando a decisão faz 7 dias (se ainda tiver motivo) ou na hora, se chegar um aviso novo. A decisão notifica cada vendedora que tinha aviso aberto do SKU, sem o comentário (que pode ter preço).

**Entregas atrasadas e cobrança** (`POST /pedidos/{id}/cobrancas`, no painel). Entrega atrasada é um item de pedido de compra `aprovado`, `enviado` ou `recebido_parcial` com quantidade pendente e data prevista antes de hoje; pedido sem data nunca atrasa. O SKU em ruptura que já tem pedido atrasado vai para o grupo das entregas, porque o problema não é comprar, é cobrar. A cobrança vale para o pedido inteiro, com nova previsão opcional, e o tira do painel até essa data (inclusive) ou, sem ela, por 7 dias (`PRAZO_DA_COBRANCA`); os dias de atraso contam sempre da data prevista original. Cada fornecedor do painel mostra o histórico de atrasos das entregas já recebidas (`GET /fornecedores/{id}/atrasos`), o primeiro dado para um dia voltar a usar o lead time.

**Notificações** (`GET /notificacoes`, o sino de toda tela). Não há processo em segundo plano: quando alguém abre o Copilot (e a cada 2 minutos com a aba visível), a rota varre as condições dos papéis da pessoa e grava **episódios de alerta** (`copilot.episodios_alerta`, migration [`0018_episodios_alerta`](alembic/versions/0018_episodios_alerta.py)): ruptura e estoque divergente por SKU e entrega atrasada por pedido para o comprador, queda de venda para o repositor. Varrer de novo não abre outro episódio; a condição que some fecha o episódio, e a que volta abre outro. Duas varreduras ao mesmo tempo não duplicam (`pg_advisory_xact_lock`, índice único parcial). Os recados (aviso ao comprador, gôndola vazia) e as respostas a eles (decisão sobre o aviso, verificação sobre a gôndola vazia, estas dirigidas à vendedora autora) entram como episódios que já nascem fechados. Não lida é a notificação aberta depois do cursor de visto da pessoa; "Marcar tudo como lido" move o cursor. A tela mostra um pop-up no canto com as novas desde a última visita, agrupadas por tipo.

**Preços para negociar** (`GET /skus/{sku}/precos`). Quando o representante quer subir o preço, a tela do SKU mostra o que o atacadista já pagou em cada pedido de compra (sem os cancelados), o preço atual de cada fornecedor e até 10 substitutos (SKUs ativos de outro produto, da mesma categoria e tamanho, pelo menor preço atual). No `ED-BEGE-CASAL-01`, por exemplo:

```json
{
  "historico": [
    {
      "data": "2026-04-24T00:00:00Z",
      "fornecedor_nome": "Katrina Têxtil",
      "preco_unitario_centavos": 8561,
      "quantidade": 180,
      "status": "recebido_total"
    }
  ],
  "precos_atuais": [
    {
      "fornecedor_id": "a8429f54-2d78-535a-a5d9-f7e8a36dbef0",
      "fornecedor_nome": "Aurora Home Center",
      "preco_unitario_reais": 8593,
      "moq_unidades": 48,
      "lead_time_dias_contratado": 40,
      "lead_time_dias_observado": 52,
      "prazo_pagamento_padrao": "30/60",
      "pedido_minimo_reais": 10000
    }
  ],
  "substitutos": [
    {
      "sku_code": "CB-OFF--CASAL-08",
      "produto_nome": "Colcha Bouti",
      "cor": "off-white",
      "tamanho": "casal",
      "preco_unitario_centavos": 7323,
      "fornecedor_nome": "Katrina Têxtil"
    }
  ]
}
```

Recortado: são três fornecedores (Aurora, Katrina a R$ 89,49 e Verdela) e nove substitutos.

O seed tem só 15 pedidos de compra, então muitos SKUs não têm histórico. O preço pago nos pedidos antigos do seed fica 1% abaixo do atual por mês de idade, para o histórico ter o que mostrar.

**Chat em contexto** (`POST /chat` com `sku_code`). Na tela do SKU, o chat lateral manda o SKU da tela. Para as intenções `situacao_sku` e `sugestao_compra`, se a pergunta não leva a nenhum SKU (nem por código, nem pelo produto que o Jev escolheu), vale o SKU da tela, com a origem `contexto` na identificação: "por que está acabando?" funciona sem repetir o produto. Pergunta que cita outro produto responde sobre o citado; as outras intenções ignoram o contexto. A intenção continua com o Jev e a regra é do código ([ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md)). O registro de decisão grava o `sku_em_contexto` (migration [`0012_sku_em_contexto`](alembic/versions/0012_sku_em_contexto.py)).

### Operação da loja: repositor e vendedora

O módulo `reposicao` é dono das verificações de gôndola, dos setores, dos avisos de gôndola vazia e das capacidades da gôndola (`copilot.verificacoes_gondola`, `copilot.setores`, `copilot.setores_sku`, `copilot.avisos_gondola` e `copilot.capacidades_gondola`, migrations `0020` a `0023`). Tudo é conta em código, sem Jev.

**Queda de venda** (`GET /reposicao/painel`). Dia aberto é o dia em que a loja vendeu alguma coisa (domingo fechado some da conta, sem calendário). A janela são os últimos `dias_observados_queda` dias abertos antes de hoje (padrão 2); a venda diária base é a média dos 28 dias abertos anteriores (`DIAS_ABERTOS_DA_BASE`). O SKU que vende ao menos `venda_diaria_minima_queda` por dia (padrão 1) entra quando a chance de vender tão pouco na janela, pela Poisson da base, fica abaixo de `limiar_queda` (padrão 1%). Os três são parâmetros da política (pergunta 11, "a validar com o comprador"). Com estoque, a suspeita é a gôndola, e o SKU vai para o painel do repositor; sem estoque, ele já está em ruptura ou entrega atrasada no painel do comprador, com o selo "Parou de vender". No seed, o tapete marrom (`TAP-MARR-4060-01`) vendia 10,3 por dia e vendeu 5 e 0 nos dois últimos dias abertos, com 392 no estoque.

**Verificação de gôndola** (`POST /skus/{sku}/verificacoes`). O repositor responde `repus`, `estava_na_gondola` ou `sem_estoque_no_deposito`, com comentário e, se for o caso, o setor corrigido. O SKU sai do painel do repositor até um dia aberto inteiro depois da verificação fechar ainda com queda. `sem_estoque_no_deposito` com disponível no ERP vira **estoque divergente** no painel do comprador, até uma decisão de compra ou até o disponível do ERP mudar; com disponível zero, não vira.

**Aviso de gôndola vazia** (`POST /avisos-gondola`, tela "Consultar e avisar"). A vendedora busca o SKU, escolhe o setor (já vem o setor conhecido do SKU) e avisa. O SKU entra no topo do painel do repositor, em "Avisos das vendedoras" (o mais antigo primeiro; um SKU com aviso e queda aparece uma vez, com as duas informações), e o papel `reposicao` é notificado. A verificação fecha o aviso e notifica a vendedora, que acompanha tudo em "Meus avisos" (`GET /avisos/meus`, os dos últimos 30 dias). Os **setores** são uma lista simples que o admin cadastra (`/ui/setores.html`); o Copilot aprende o setor de cada SKU pelos avisos e pelas verificações, e o seed já traz o setor dos SKUs dos cenários.

**Mix de gôndola** (`GET /reposicao/produtos/{id}/mix`). O repositor informa quantas peças do produto cabem na gôndola, e o Copilot divide esse espaço entre as cores e tamanhos pela **participação nas vendas** dos últimos `dias_mix_gondola` dias abertos (padrão 90, pergunta 12): maiores restos, ao menos uma peça por SKU com estoque, nunca mais do que o disponível (o que sobra vai para os outros) e divisão igual quando o produto não vendeu nada. A capacidade fica lembrada por produto. No seed, o Tapete Banheiro com 12 lugares dá 4 marrons (45% da venda), 3 cinzas, 2 azuis, 2 beges e 1 branco (8%). A tela do SKU do comprador mostra a mesma participação, para ele comprar a grade na proporção do que vende.

### Usuários e papéis

O módulo `usuarios` ([ADR-0007](docs/adr/0007-usuarios-sessao-e-papeis.md), migrations `0014` e `0015`) guarda as pessoas, as sessões e as tentativas de login. Senha com argon2id; o token da sessão vai num cookie `HttpOnly` e o banco guarda só o sha256 dele; a sessão dura 30 dias, renovados a cada uso; cinco senhas erradas em 15 minutos bloqueiam o e-mail por 15 minutos (429). Quatro papéis fixos, e uma pessoa pode ter vários: `comprador`, `vendas`, `reposicao` e `admin`. O admin cadastra as pessoas, troca papéis, redefine senhas e desativa (o que revoga todas as sessões; o que a pessoa registrou fica). Avisos, decisões, cobranças, verificações, capacidades e perguntas do chat gravam o `usuario_id` de quem fez.

### Telas por papel

HTML, CSS e JS puros, sem build, servidos pelo próprio app em `/ui/`. O cabeçalho de toda tela logada tem o menu das telas do papel, o sino das notificações e o nome da pessoa, que leva à tela "Minha conta" (trocar a senha); quem abre uma tela de outro papel cai na tela inicial do seu. `tests/test_ui.py` confere que as páginas e os assets respondem, que cada tela monta o cabeçalho do seu papel, que o menu só aponta para telas que existem e que todo endpoint chamado pelos `.js` existe na OpenAPI do app.

**Comprador** (Painel, Estoque e Política, com o chat lateral):

- **Painel** (`/ui/`): filtros (busca, categoria, motivo, fornecedor) guardados na URL, contadores por grupo e os cards de cada grupo: "Pedidos da equipe de vendas" (o aviso, quem avisou e quando), "Estoque divergente" (o recado do repositor), "Entregas atrasadas" (por fornecedor, com o histórico de atrasos, os pedidos, os SKUs e o botão "Cobrei o fornecedor"), "Em ruptura" ("Zerado: já está faltando na loja", "Segura 4 dias") e os outros grupos. Cada card abre a tela do SKU. No fim, recolhidos, os decididos nos últimos 7 dias.
- **Estoque** (`/ui/estoque.html`): todos os SKUs ativos numa tabela (cartões no celular), com a mesma barra de filtros, situação, ordenação e paginação.
- **Tela do SKU** (`/ui/sku.html?sku=<código>`): situação em números grandes, entregas pendentes com as cobranças, sugestão de compra com alertas e memória de cálculo, sinais do corpus, vendas de 12 meses, participação nas vendas do produto e preços para negociar; ao lado, os avisos, as verificações de gôndola, o formulário "O que você decidiu?" e as decisões anteriores.
- **Política** (`/ui/politica.html`): o onboarding da [ADR-0003](docs/adr/0003-politica-de-compra-configuravel.md), cada pergunta preenchida com o valor ativo, inclusive a sensibilidade da queda de venda e o período do mix de gôndola.
- **Chat lateral** (botão "Perguntar ao Copilot"): uma conversa, com perguntas sugeridas e a resposta com as citações não confirmadas em vermelho; em "Como o Copilot chegou nisso", o entendimento, as fichas, as sugestões, os sinais e as citações. Na tela do SKU, pergunta no contexto do SKU.

![Painel do comprador com o sino aberto: rupturas, estoque divergente e entrega atrasada](docs/img/notificacoes.png)

![Tela de Estoque com todos os SKUs, filtros, ordenação pelos dias que o estoque segura e paginação](docs/img/estoque.png)

![Tela do SKU do tapete marrom com a situação, a sugestão, as vendas, a verificação do repositor, a decisão de compra e a participação nas vendas do produto](docs/img/sku.png)

**Equipe de vendas** ("Consultar e avisar", `/ui/aviso.html`, feita para o celular, sem chat): busca do SKU; a disponibilidade com o selo "Tem", "Tem pouco" ou "Acabou", o número grande e as compras a caminho ("Vem 24 unidades, chega por volta de 11/10", ou "Atrasada"); os botões "Avisar o comprador" (acabou ou vende muito) e "Gôndola vazia" (setor e comentário); e "Meus avisos", com selos como "Aguardando o comprador", "Vai comprar 48 peças", "Repôs a gôndola" ou "Não tinha no depósito".

![Consulta da vendedora no celular: tem pouco, 18 no estoque, vem 24 unidades por volta de 11/10](docs/img/consulta.png) ![Meus avisos da vendedora no celular: o aviso ao comprador aguardando e a gôndola vazia reposta](docs/img/meus-avisos.png)

**Repositor** (Painel do repositor e Montar gôndola):

- **Painel do repositor** (`/ui/reposicao.html`): busca e filtros de setor e categoria; "Avisos das vendedoras" no topo e "Pararam de vender e têm estoque" embaixo, cada card com a frase "Vendia 10,3 por dia. Vendeu 5 na sexta e 0 no sábado.", três números grandes, o setor, os três botões da verificação com comentário e o link "Montar a gôndola deste produto".
- **Montar gôndola** (`/ui/gondola.html`): busca do produto e, nele, quantas peças cabem, com "Lembrar este número", e quantas peças pôr de cada cor, com a participação nas vendas.

![Painel do repositor com o tapete marrom que parou de vender e o pop-up da notificação](docs/img/reposicao.png)

![Mix de gôndola do Tapete Banheiro com 12 peças: 4 marrons, 3 cinzas, 2 azuis, 2 beges e 1 branco](docs/img/gondola.png)

**Admin** (Usuários e Setores): cadastrar pessoas com os papéis, editar papéis, redefinir senha, desativar e reativar (`/ui/usuarios.html`); adicionar, renomear, desativar e reativar setores (`/ui/setores.html`).

![Tela de usuários do admin, com as pessoas e os papéis](docs/img/usuarios.png)

![Onboarding da política de compra, com as perguntas de estoque máximo, datas fortes e ruptura](docs/img/politica.png)

As telas foram capturadas com `scripts/capturar_tela.py`, que entra pelo `POST /login`, põe o cookie da sessão no Chrome headless pelo DevTools e grava o PNG (1280 px de largura no computador e 390 px no celular), contra o seed de 2026-10-04 seguindo o [roteiro de demo](docs/demo.md): `uv run python -m scripts.capturar_tela http://localhost:8000/ui/ painel.png --email carla@copilot.local --senha copilot-local --clicar button.popup-fechar`. `--celular`, `--clicar <seletor>` e `--executar <js>` emulam o celular, clicam e digitam antes da captura.

### Limites conhecidos da plataforma

- **Notificação só dentro do Copilot.** Não há WhatsApp, e-mail nem push, e nenhum processo em segundo plano: a notificação nasce quando alguém abre o Copilot, então a hora do episódio pode ser depois da hora em que o SKU entrou em ruptura.
- **Sem estoque por local.** O ERP fake tem um saldo só, sem separar gôndola e depósito; a queda de venda é o jeito de achar gôndola vazia sem esse dado. Dia aberto é heurística: feriado aberto com pouca venda pode dar alarme falso.
- **Parâmetros chutados.** A sensibilidade da queda de venda, o período do mix, o prazo da cobrança e as outras suposições da spec (seção "Pormenores e suposições") esperam o comprador em [`perguntas-comprador.md`](.scratch/sugestao-compra/perguntas-comprador.md), perguntas 15 a 29.
- **Regras de cálculo ainda do MVP.** O giro não desconta os meses de ruptura, o mix usa a venda passada sem corrigir os dias em que faltou e o ciclo de compra é um só para todos os SKUs (2 meses por padrão).
- **Prazos fixos.** Os 7 dias da decisão e da cobrança são constantes do código, não parâmetros da política.
- **Histórico de preço ralo no seed.** Ver acima; com o ERP real, ele vem dos pedidos de verdade.
- **Sem integração com o Maos.** O similar da vendedora, o setor por SKU e a data prevista confiável do pedido dependem dele (ver o [roadmap](.scratch/plataforma/roadmap.md)).

A documentação interativa (OpenAPI) fica em `http://localhost:8000/docs`.

## Estrutura de módulos

Árvore de código:

```
src/
├── erp_adapter/      Port + PostgresERPAdapter + InMemoryERPAdapter (única fronteira com o ERP)
├── catalog/          SKU, produto, fornecedor
├── inventory/        estoque atual, cobertura, abaixo do piso
├── sales/            giro médio, histórico de vendas, sazonalidade
├── ficha_sku/        compõe a ficha completa de um SKU (usada por /analise)
├── politica_compra/  política de compra versionada (schema copilot)
├── purchasing/       sugestão de pedido (quanto, de quem, memória de cálculo, alertas) e referências de preço (histórico pago, preço atual, substitutos)
├── ai/               corpus, ingestão no pgvector, busca com o filtro do Jev, sinais do corpus, verificação de citações, chat (entendimento, identificação dos SKUs, roteamento, contexto, redator Claude, registro de decisão)
├── painel/           painel de alertas, tela de Estoque, consulta da vendedora, avisos da equipe de vendas, decisões de compra e cobranças de entrega (copilot.avisos, copilot.decisoes_compra e copilot.cobrancas_entrega)
├── reposicao/        queda de venda, painel do repositor, verificações de gôndola, setores, avisos de gôndola vazia e mix de gôndola
├── notificacoes/     episódios de alerta, varredura e caixa de notificações de cada usuário (copilot.episodios_alerta)
├── usuarios/         usuários, papéis, sessões e login (copilot.usuarios, copilot.sessoes e copilot.tentativas_login)
├── api/              camada HTTP (FastAPI routers, DTOs de resposta)
├── ui/               UI estática servida em /ui (HTML, CSS e JS puros, sem build)
├── db/               config, engine, health-check
└── main.py           bootstrap FastAPI

scripts/              seed.py, criar_admin.py, capturar_tela.py, benchmark_painel.py, ingerir_corpus.py, spike_jev.py, avaliar_recuperacao.py, avaliar_entendimento.py, avaliar_sinais.py, avaliar_citacoes.py, avaliar_conflitos.py, calibracao.py (regra de calibração dos limiares), relatorio_registros.py, rodar_casos_chat.py, jev_check.py, dependencias.py, db-init (extensões Postgres)
corpus/               documentos do RAG (markdown com frontmatter)
evals/                casos rotulados (perguntas, intenções, trechos, sinais, citações, pares de conflito) e respostas cruas do Jev em evals/resultados/
alembic/              migrations versionadas
tests/                fakes.py + testes cross-módulo + tests/smoke/ end-to-end
```

Grafo de dependência (setas: "depende de"), com os serviços externos:

```mermaid
flowchart TD
    api[api] --> painel[painel]
    api --> ai[ai]
    api --> ficha_sku[ficha_sku]
    painel --> purchasing[purchasing]
    painel --> reposicao[reposicao]
    painel --> notificacoes[notificacoes]
    reposicao --> notificacoes
    reposicao --> ficha_sku
    notificacoes --> usuarios[usuarios]
    ai --> painel
    ai --> purchasing
    purchasing --> ficha_sku
    purchasing --> catalog
    purchasing --> politica_compra[politica_compra]
    purchasing -- pedidos de compra --> erp_adapter[erp_adapter]
    ficha_sku --> catalog[catalog]
    ficha_sku --> inventory[inventory]
    ficha_sku --> sales[sales]
    inventory --> sales
    catalog --> erp_adapter
    inventory --> erp_adapter
    sales --> erp_adapter

    ai --> Jev[("Jev (TypeSafe)")]
    ai --> Claude[("Claude (Anthropic)")]
    erp_adapter --> Postgres[("Postgres + pgvector<br/>schemas erp e copilot")]
    politica_compra --> Postgres
    painel --> Postgres
    reposicao --> Postgres
    notificacoes --> Postgres
    usuarios --> Postgres
    ai --> Postgres

    classDef externo fill:#eef,stroke:#88a
    class Jev,Claude,Postgres externo
```

O grafo mostra só as arestas principais. As chamadas diretas de `api`, `painel`, `ai` e `purchasing` para os módulos de baixo estão na lista:

- `api` depende de `usuarios` (login, sessão e o papel de cada rota, por `exige_papel`), `painel` (para `/painel`, `/estoque`, `/avisos`, as decisões, as cobranças e a disponibilidade), `reposicao` (painel do repositor, verificações, setores, avisos de gôndola vazia e mix), `notificacoes` (o sino), `purchasing` (para `/sugestao-compra` e `/precos`), `ficha_sku` (para `/analise`), `politica_compra` (para `/politica-compra` e o piso padrão de `/abaixo-do-piso`) e `ai` (para `/rag/busca`, `/sugestao-compra/sinais` e `/chat`), e chama `catalog`, `inventory`, `sales` direto nos endpoints de leitura simples. A UI (`src/ui/`) não é módulo de domínio: são arquivos estáticos que o `main.py` serve e que só falam com a API por HTTP.
- `painel` depende de `catalog` (SKUs ativos e o SKU do aviso), `ficha_sku` (o retrato em lote), `inventory` (cobertura e entregas atrasadas), `purchasing` (`sugerir_pedidos` sobre o retrato), `politica_compra` (motivos de alerta e piso), `reposicao` (queda de venda para o selo "Parou de vender" e verificações para o estoque divergente), `notificacoes` (as condições do comprador e os eventos dos avisos e decisões) e `usuarios` (o autor), e fala direto com `copilot.avisos`, `copilot.decisoes_compra` e `copilot.cobrancas_entrega`, atrás dos ports `AvisosRepositorio`, `DecisoesRepositorio` e `CobrancasRepositorio`. Não chama o `ai`. Depende dele a `api` e o `ai` (só a leitura do painel, na intenção de alertas e avisos).
- `reposicao` depende de `catalog`, `ficha_sku`, `inventory`, `sales` (vendas diárias em lote), `politica_compra` (parâmetros da queda e do mix), `notificacoes` e `usuarios`, e fala direto com as tabelas dele atrás de um port por tabela. Não depende do `painel`: o `painel` é que lê dele.
- `notificacoes` depende só de `usuarios` (o cursor de visto e o destino). Não sabe calcular nenhuma condição: quem é dono de cada uma monta a lista de condições e pede a varredura.
- `usuarios` não depende de nenhum módulo de domínio.
- `purchasing` depende de `catalog`, `ficha_sku`, `inventory`, `sales` e `politica_compra`. Do `erp_adapter`, só lê os pedidos de compra (`itens_de_pedido_de`, para o histórico de preço), que não têm módulo de leitura próprio. O Copilot não escreve no ERP.
- `politica_compra` fala direto com o schema `copilot` do Postgres. Não passa pelo `erp_adapter`, porque a política é dado do Copilot, não do ERP.
- `ai` fala direto com `copilot.trechos_corpus` (pgvector), atrás do port `TrechosRepositorio`, com `copilot.registros_decisao`, atrás do port `RegistrosDecisao`, com a API da TypeSafe, atrás do port `DecisionModel`, e com a Anthropic (Claude), atrás do port `Redator`. No chat, só lê dos outros módulos: `catalog` (lista de SKUs), `ficha_sku` (ficha completa), `purchasing` (só `sugerir_pedido`) e `politica_compra` (política ativa). Nada no `ai` escreve no ERP.
- `ficha_sku` depende de `catalog`, `inventory`, `sales` e não fala com o `erp_adapter` direto.
- `inventory` depende de `sales` (cobertura precisa de giro).
- `catalog`, `inventory`, `sales` e `purchasing` dependem de `erp_adapter`.
- `erp_adapter` importa só os DTOs de domínio (`catalog.schemas`, `inventory.schemas`, `sales.schemas`) para devolvê-los prontos. O DTO dos itens de pedido (`ItemDePedido`) é dele (`erp_adapter/schemas.py`), para o `purchasing` depender do `erp_adapter` sem ciclo. Os serviços desses módulos ele não chama.
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
