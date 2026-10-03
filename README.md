# Copilot de Compras

Assistente de decisão de compras para um atacadista de cama, mesa e banho: sugere o que comprar, quanto, de quem e quando, a partir de um ERP simulado e de um corpus de documentos (contratos, atas, políticas), sempre com o comprador chefe decidindo no fim. Vocabulário, decisões e restrições de domínio vivem em [`CONTEXT.md`](CONTEXT.md).

**MVP completo (M0-M8 do [roadmap](.scratch/copilot-compras/roadmap.md)).** A sugestão de pedido é determinística: giro, cobertura, em trânsito, lead time e MOQ calculados em código, com os parâmetros de uma política de compra que o próprio comprador preenche num onboarding. Em volta dela, a IA segue a [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md): o Jev (TypeSafe) toma decisões tipadas com confiança (intenção da pergunta, relevância de trecho, sinais do corpus como atraso do fornecedor e encalhe, verificação de citações), o código executa e um LLM (Claude) só redige a resposta do chat.

O produto segue o trabalho do comprador chefe, do alerta à decisão ([ADR-0005](docs/adr/0005-copilot-termina-na-decisao-de-compra.md)): a equipe de vendas avisa pelo celular que um SKU acabou ou está vendendo muito; o **painel de alertas** junta esses avisos com os SKUs que vão faltar segundo a política; a **tela do SKU** reúne situação, vendas, sugestão de pedido, sinais do corpus e preços para negociar com o representante, com o chat ao lado já no contexto do SKU; e o fluxo termina numa **decisão de compra** (`vou_comprar`, `negociando` ou `nao_comprar_agora`). O Copilot não cria pedido de compra: o pedido sai no ERP real do atacadista, depois da negociação. Para ver tudo funcionando em 5 a 8 minutos, siga o [roteiro de demo](docs/demo.md).

![Painel de alertas com os SKUs que acabam antes da compra chegar e um aviso da equipe de vendas](docs/img/painel.png)

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

# 3. Popula o ERP fake com dados sintéticos reprodutíveis
uv run python -m scripts.seed

# 4. Ingere o corpus em copilot.trechos_corpus (idempotente: só reprocessa documento novo ou alterado)
uv run python -m scripts.ingerir_corpus

# 5. Cria o primeiro admin (pede a senha no terminal)
uv run python -m scripts.criar_admin --nome "Seu nome" --email voce@loja.com
```

Toda tela e toda rota, menos `/health` e `/login`, exigem login ([ADR-0007](docs/adr/0007-usuarios-sessao-e-papeis.md)). Para testar outro papel localmente, crie a pessoa com `--papeis` (`comprador`, `vendas`, `reposicao`, `admin`, separados por vírgula). Fora do ambiente local, defina `AMBIENTE=producao` para o cookie de sessão sair com `Secure`.

A ingestão baixa o modelo de embedding para `.cache/fastembed` na primeira vez. Os endpoints que usam o Jev (`/rag/busca`, `/chat` e `/skus/{sku_code}/sugestao-compra/sinais`) também precisam da `JEV_KEY` (chave da API da TypeSafe) no `.env`: copie o `.env.example` e preencha. Sem a chave, só esses respondem 503. A chave do redator (`ANTHROPIC_API_KEY`) é opcional: sem ela, o chat responde com os dados que reuniu, sem redação.

O app fica em `http://localhost:8000`. Confirme com:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok"}
```

A UI fica em `http://localhost:8000/ui/` (a raiz redireciona para o painel de alertas). A página da equipe de vendas é `http://localhost:8000/ui/aviso.html`. Fora do Docker, suba só o banco (`docker compose up -d db`) e rode o app com `uv run uvicorn src.main:app`.

### Resetar o ambiente local

O seed (`uv run python -m scripts.seed`) apaga e recria só o schema `erp`. As tabelas do Copilot (schema `copilot`) não são tocadas por ele e acumulam o que o uso grava: avisos da equipe de vendas, decisões de compra, registros de decisão do chat e versões da política. Para voltar ao estado inicial:

```bash
uv run python -m scripts.seed
docker compose exec db psql -U copilot -d copilot -c "
  TRUNCATE copilot.avisos, copilot.decisoes_compra, copilot.registros_decisao;
  DELETE FROM copilot.politicas_compra WHERE versao > 1;"
```

O painel volta a ter só os motivos de alerta calculados, os registros de decisão ficam vazios e a política volta à v1 (a da migration). Os trechos do corpus não precisam de reset: a ingestão é idempotente.

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
- **Smoke end-to-end** (`tests/smoke/`) - sobem o app real contra o Postgres real com seed populado e o corpus ingerido com o embedding de verdade.
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
# o aviso e a decisão de compra que o smoke do painel grava são apagados no fim)
uv run pytest tests/smoke/

# Todos os testes marcados como smoke, incluindo tests/test_seed_smoke.py
# (este exige alembic upgrade head antes)
uv run pytest -m smoke

# Tudo
uv run pytest
```

## Endpoints

| Método | Rota | O que devolve |
| ------ | ---- | ------------- |
| `GET` | `/health` | Saúde do app e do banco. |
| `GET` | `/painel` | Painel de alertas calculado na hora: `alertas` (SKUs com aviso aberto ou motivo de alerta, na ordem de urgência), `decididos` (com decisão de compra vigente) e `skus_com_erro`. 503 com o banco fora do ar. |
| `POST` | `/avisos` | Aviso da equipe de vendas (`sku_code`, `tipo` `acabou` ou `vendendo_muito`, `avisado_por`, `comentario` opcional). 201; 404 sem o SKU; 422 com o SKU inativo. |
| `GET` | `/skus?busca=...` | Busca da página de aviso: até 20 SKUs ativos com todas as palavras no código, nome, cor ou tamanho, sem diferenciar acento nem maiúscula (mínimo de 2 caracteres). |
| `GET` | `/skus/{sku_code}/avisos` | Avisos abertos do SKU (sem decisão de compra posterior), do mais recente para o mais antigo. |
| `GET` | `/skus/{sku_code}/decisoes` | Decisões de compra do SKU, da mais recente para a mais antiga. |
| `POST` | `/skus/{sku_code}/decisoes` | Registra a decisão de compra (`tipo`, `decidido_por`, `quantidade` em `vou_comprar`, `motivo` em `nao_comprar_agora`, `comentario` opcional), com a sugestão e a versão da política do momento. 201; 404 sem o SKU; 422 nas validações. Não cria pedido de compra. |
| `GET` | `/skus/{sku_code}/precos` | Referências para negociar: preço pago em cada pedido de compra (sem os cancelados), preço atual por fornecedor e até 10 substitutos (outro produto da mesma categoria e tamanho) pelo menor preço. |
| `GET` | `/skus/{sku_code}/analise` | Análise composta: nome, categoria, cor, tamanho, estoque, em trânsito, giro, cobertura, fornecedores. |
| `GET` | `/skus/abaixo-do-piso?dias=20` | SKUs com cobertura abaixo do piso de alerta. Sem `dias`, usa o `piso_alerta_dias` da política ativa. |
| `GET` | `/skus/{sku_code}/sugestao-compra` | Sugestão de pedido: quantidade, fornecedor, valor, memória de cálculo e alertas. |
| `GET` | `/skus/{sku_code}/sugestao-compra/sinais` | Sinais do corpus sobre o fornecedor e o produto da sugestão, com os trechos de origem. Lista vazia quando a sugestão não tem fornecedor; 503 sem o Jev. |
| `GET` | `/skus/{sku_code}/vendas?meses=12` | Série mensal de vendas. |
| `GET` | `/skus/{sku_code}/sazonalidade` | Multiplicadores mês-a-mês (1 = neutro). |
| `GET` | `/skus/{sku_code}/fornecedores` | Preço, MOQ e lead time por fornecedor. |
| `GET` | `/politica-compra` | Política de compra ativa (`versao`, `criada_em`, `parametros`). |
| `PUT` | `/politica-compra` | Recebe os parâmetros completos, inclusive os motivos de alerta do painel, valida e grava uma versão nova (201, ou 422 se inválida). |
| `GET` | `/rag/busca?q=...&k=30` | Trechos do corpus mais parecidos com a pergunta, classificados pelo filtro do Jev, e os conflitos entre eles. |
| `POST` | `/chat` | Responde em texto a pergunta do comprador chefe, com o entendimento do Jev, a faixa de confiança, a ação, os dados que foram ao redator (sugestões com os sinais do corpus) e a verificação das citações. `sku_code` opcional: o SKU da tela de onde ele pergunta (404 se não existe). |
| `GET` | `/chat/registros?limite=20` | Registros de decisão do chat, do mais recente para o mais antigo (`limite` de 1 a 100). |
| `GET` | `/ui/` | UI sem build: painel de alertas, tela do SKU, página de aviso da equipe de vendas, onboarding da política e o chat lateral. `/` redireciona para cá. |

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

Como no `/analise`, os números e os alertas dependem da data em que o seed rodou.

A sugestão é calculada na hora e não é gravada. Quando não há o que comprar, `quantidade` é 0 e `motivo` diz por quê (`sku_novo`, `sem_giro`, `sem_fornecedor` ou `acima_do_ponto_de_reposicao`). `calculo` fica `null` nos três primeiros motivos. `politica_versao` diz com qual versão da política a conta foi feita.

### Política de compra

O mecanismo da sugestão (contar o que está em trânsito, descontar o consumo durante o lead time, respeitar o MOQ, nunca esconder violação de teto) é fixo no código. Os parâmetros de estratégia (teto, pisos, ciclo de compra, qual lead time usar, critério de fornecedor, sazonalidade, regra de SKU novo, motivos de alerta do painel) são do comprador chefe e ficam na política de compra, versionada em `copilot.politicas_compra`. Cada `PUT /politica-compra` cria uma versão nova, e a ativa é a de maior `versao`. A v1 nasce na migration com os valores da política v3 do corpus; a migration `0009` a levou ao ciclo de compra de 2 meses ("no mínimo 60 dias de cobertura de venda", pedido do dev para o MVP) e aos motivos de alerta padrão. Como piso de reposição mais ciclo fecha exatamente no teto de 3 meses, o cálculo aceita passar do teto por menos de uma unidade, que é só o arredondamento para unidade inteira.

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

O Copilot segue o trabalho do comprador chefe, do alerta à decisão ([ADR-0005](docs/adr/0005-copilot-termina-na-decisao-de-compra.md)). O módulo `painel` é dono dos avisos da equipe de vendas (`copilot.avisos`, migration [`0010_avisos`](alembic/versions/0010_avisos.py)), das decisões de compra (`copilot.decisoes_compra`, migration [`0011_decisoes_compra`](alembic/versions/0011_decisoes_compra.py)) e da composição do painel de alertas. O Copilot não escreve no ERP: o pedido de compra sai no ERP real, depois da negociação com o representante.

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
    loop cada SKU ativo
        M->>U: sugerir_pedido (determinístico, sem Jev)
    end
    M-->>C: alertas (aviso ou ruptura primeiro) e decididos
    C->>A: tela do SKU: análise, sugestão, sinais, preços, vendas, avisos e decisões
    C->>A: POST /chat com o sku_code da tela
    C->>A: POST /skus/{sku}/decisoes (vou_comprar, negociando ou nao_comprar_agora)
    A->>M: registrar_decisao
    M->>U: sugestão do momento (quantidade e versão da política)
    M->>P: copilot.decisoes_compra
```

**Painel de alertas** (`GET /painel`, a home da UI). Calculado na hora, sem estado próprio, com a política ativa: para cada SKU ativo, a sugestão de pedido e a cobertura atual (só o disponível). Os **motivos de alerta** de um SKU são os alertas da sugestão que estão nos `motivos_de_alerta` da política, mais `abaixo_do_piso_alerta` quando a cobertura atual fica abaixo do `piso_alerta_dias`. O padrão é ruptura antes da chegada e abaixo do piso de alerta; o comprador muda na pergunta 10 da tela de política (migration [`0009_motivos_de_alerta`](alembic/versions/0009_motivos_de_alerta.py)). O SKU entra no painel se tem aviso aberto ou algum motivo. Vêm primeiro os com aviso aberto ou ruptura antes da chegada e, em cada grupo, a menor cobertura na chegada sem a compra (os SKUs sem cálculo no fim do grupo, o código desempata). Um SKU sem a linha de estoque no ERP vai para `skus_com_erro` em vez de derrubar o painel. Com o seed, o painel leva uns 2 s e traz 9 SKUs, todos com ruptura antes da chegada. O painel não chama o Jev.

```json
{
  "sku_code": "JDCP-ROSA-SOLTEIRO-10",
  "produto_nome": "Jogo de Cama Percal 200 fios",
  "cor": "rosa",
  "tamanho": "solteiro",
  "disponivel": 62,
  "cobertura_atual_meses": 1.1923076923076923,
  "cobertura_na_chegada_sem_compra_meses": -0.7743589743589744,
  "motivos": ["ruptura_antes_da_chegada"],
  "quantidade_sugerida": 156,
  "fornecedor_sugerido": "Verdela Home",
  "avisos_abertos": 0,
  "ultimo_aviso": null,
  "so_por_aviso": false
}
```

**Aviso da equipe de vendas** (`POST /avisos`, página `/ui/aviso.html`). A vendedora busca o SKU pelo nome, cor ou tamanho (`GET /skus?busca=`, sem diferenciar acento nem maiúscula), marca `acabou` ou `vendendo_muito`, escreve um comentário se quiser e envia. O SKU entra no painel na hora, no primeiro grupo, mesmo quando o cálculo não vê problema (`so_por_aviso`), porque a loja pode estar vendo algo que o histórico não mostra. SKU inativo não aceita aviso (422).

**Decisão de compra** (`POST /skus/{sku}/decisoes`, na tela do SKU). `vou_comprar` exige a quantidade (maior que zero), `nao_comprar_agora` exige o motivo, e `negociando` só tira o SKU do painel enquanto o comprador conversa com o representante. A decisão guarda a quantidade sugerida e a versão da política do momento, para comparar depois o que o Copilot sugeriu com o que o comprador decidiu. Nada é atualizado: **aviso aberto** é o que não tem decisão do mesmo SKU depois dele, e **decisão vigente** é a mais recente do SKU, com menos de 7 dias (`PRAZO_DA_DECISAO`) e sem aviso posterior. Com decisão vigente, o SKU sai dos alertas e vai para `decididos`; volta quando a decisão faz 7 dias (se ainda tiver motivo) ou na hora, se chegar um aviso novo.

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

### UI: `/ui/`

HTML, CSS e JS puros, sem build, servidos pelo próprio app. A navegação do comprador é Painel e Política, com o botão do chat no cabeçalho.

- **Painel** (`/ui/`): no topo, quatro contadores (pedidos da equipe de vendas, vão faltar antes da compra chegar, outros alertas e decididos nos últimos 7 dias) e os botões para abrir e copiar o link da página das vendedoras. Embaixo, os SKUs em três grupos de cards, na ordem do painel: "Pedidos da equipe de vendas" (com aviso aberto: o tipo, quem avisou, quando e o comentário), "Vão faltar antes da compra chegar" e "Outros alertas". Cada card diz em frase o que acontece ("Acaba cerca de 23 dias antes de uma compra feita hoje chegar"), o estoque, quanto tempo ele dura, os motivos e a sugestão, e abre a tela do SKU. No fim, a seção recolhida "Decididos nos últimos 7 dias". Mensagens claras para painel vazio e para banco fora do ar (503).
- **Tela do SKU** (`/ui/sku.html?sku=<código>`): à esquerda, a situação do estoque em números grandes (em estoque, a caminho, vende por mês, quanto o estoque dura), a sugestão de compra com alertas e memória de cálculo (ou o motivo quando é zero), o que os documentos dizem (sinais do corpus), as vendas dos últimos 12 meses em barras (mês sem venda marcado como possível ruptura) e os preços para negociar. À direita, os avisos da equipe de vendas, o formulário "O que você decidiu?" e as decisões anteriores. Os blocos carregam em paralelo e os sinais do corpus chegam por último, sem bloquear o resto; com o Jev fora do ar, o bloco mostra "indisponível". O formulário muda os campos conforme o tipo e, depois de registrar, volta ao painel.
- **Aviso** (`/ui/aviso.html`): a página da equipe de vendas, feita para celular, sem navegação e sem chat. Busca com espera curta, dois botões grandes para o tipo, comentário, nome lembrado no navegador e confirmação na própria página, pronta para o próximo aviso.
- **Política** (`/ui/politica.html`): o onboarding da [ADR-0003](docs/adr/0003-politica-de-compra-configuravel.md). As perguntas 1 a 9 de [`perguntas-comprador.md`](.scratch/sugestao-compra/perguntas-comprador.md) na linguagem do comprador e a pergunta 10, sobre o que põe um produto no painel de alertas, cada uma preenchida com o valor ativo. Salvar grava uma versão nova da política (ou mostra o erro de validação com o número da pergunta); o painel usa a versão nova na próxima vez que abrir. As perguntas 11 a 15 aparecem só para leitura, como "como o sistema entende o ERP".
- **Chat lateral** (botão "Perguntar ao Copilot" no cabeçalho do painel, da tela do SKU e da política): uma conversa, com perguntas sugeridas para começar (na tela do SKU, sobre o próprio produto) e a resposta em texto com as citações não confirmadas em vermelho. Em "Como o Copilot chegou nisso", recolhido, ficam o entendimento (intenção, confiança, faixa, ação, SKUs), as fichas, as sugestões com os alertas e os sinais, as citações com o veredito e os trechos usados. Mostra o SKU em contexto, quando há. A largura se ajusta arrastando a borda, e o botão "Tela cheia" expande; no celular, abre em tela cheia.

A tela do SKU, com a situação, a sugestão, os sinais do corpus, as vendas e a decisão de compra ao lado:

![Tela do SKU com a situação do estoque, a sugestão de pedido com alertas, o sinal de demanda sazonal do corpus, as vendas de 12 meses e, ao lado, o aviso aberto e o formulário da decisão de compra](docs/img/sku.png)

A página de aviso, no celular:

![Página de aviso da equipe de vendas no celular, com a busca do produto, os dois botões de tipo, o comentário e o nome](docs/img/aviso.png)

O onboarding da política, com cada pergunta preenchida com o valor da versão ativa:

![Onboarding da política de compra, com as perguntas de estoque máximo, datas fortes e estoque mínimo](docs/img/politica.png)

As telas foram capturadas com o Chrome headless (`--screenshot --virtual-time-budget=20000`; 1280x1000 no painel, 1280x1400 na tela do SKU, 1280x900 na política e 390x844 na página de aviso, dentro de um iframe porque o headless não abre janela tão estreita) contra o seed e o corpus ingerido, com um aviso de demonstração no `ED-BEGE-CASAL-01`. O chat depende de digitar uma pergunta, o que a captura por URL não faz, e aparece neste README pelos exemplos reais em texto.

O nome de quem avisa e de quem decide fica no `localStorage` do navegador só por conveniência. `tests/test_ui.py` confere que as páginas e os assets respondem, que todo endpoint chamado pelos `.js` existe na OpenAPI do app e que a página de aviso não tem navegação nem chat.

### Limites conhecidos do fluxo do comprador

- **Sem login.** A vendedora e o comprador informam o nome à mão; qualquer um com o link registra aviso e decisão.
- **O painel é o único canal.** Não há notificação por e-mail, WhatsApp ou push: o comprador só vê um aviso quando abre o Copilot.
- **Painel calculado a cada abertura.** O tempo cresce com o número de SKUs ativos (uns 2 s com os 80 do seed), porque calcula a sugestão de cada um. Se ficar lento, o caminho é cache por requisição no adapter Postgres, não guardar o painel.
- **Regras de cálculo ainda do MVP.** O giro não desconta os meses de ruptura ("quanto vendia quando o estoque estava saudável") e o ciclo de compra é um só para todos os SKUs (2 meses por padrão). Com piso de 30 dias, ciclo de 2 meses e teto de 3, a compra cai exatamente no teto: o cálculo tolera menos de uma unidade acima dele, do arredondamento, e só o MOQ viola o teto de verdade.
- **Prazo da decisão fixo.** Os 7 dias são uma constante do código, não parâmetro da política.
- **Histórico de preço ralo no seed.** Ver acima; com o ERP real, ele vem dos pedidos de verdade.

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
├── painel/           painel de alertas, avisos da equipe de vendas e decisões de compra (copilot.avisos e copilot.decisoes_compra)
├── api/              camada HTTP (FastAPI routers, DTOs de resposta)
├── ui/               UI estática servida em /ui (HTML, CSS e JS puros, sem build)
├── db/               config, engine, health-check
└── main.py           bootstrap FastAPI

scripts/              seed.py, ingerir_corpus.py, spike_jev.py, avaliar_recuperacao.py, avaliar_entendimento.py, avaliar_sinais.py, avaliar_citacoes.py, avaliar_conflitos.py, calibracao.py (regra de calibração dos limiares), relatorio_registros.py, rodar_casos_chat.py, jev_check.py, dependencias.py, db-init (extensões Postgres)
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
    ai --> Postgres

    classDef externo fill:#eef,stroke:#88a
    class Jev,Claude,Postgres externo
```

O grafo mostra só as arestas principais. As chamadas diretas de `api`, `painel`, `ai` e `purchasing` para os módulos de baixo estão na lista:

- `api` depende de `painel` (para `/painel`, `/avisos` e as decisões), `purchasing` (para `/sugestao-compra` e `/precos`), `ficha_sku` (para `/analise`), `politica_compra` (para `/politica-compra` e o piso padrão de `/abaixo-do-piso`) e `ai` (para `/rag/busca`, `/sugestao-compra/sinais` e `/chat`), e chama `catalog`, `inventory`, `sales` direto nos endpoints de leitura simples. A UI (`src/ui/`) não é módulo de domínio: são arquivos estáticos que o `main.py` serve e que só falam com a API por HTTP.
- `painel` depende de `catalog` (SKUs ativos e o SKU do aviso), `inventory` (disponível e cobertura atual), `purchasing` (só `sugerir_pedido`) e `politica_compra` (motivos de alerta e piso), e fala direto com `copilot.avisos` e `copilot.decisoes_compra`, atrás dos ports `AvisosRepositorio` e `DecisoesRepositorio`. Não chama o `ai`. Nada depende dele além da `api`.
- `purchasing` depende de `catalog`, `ficha_sku`, `inventory`, `sales` e `politica_compra`. Do `erp_adapter`, só lê os pedidos de compra (`itens_de_pedido_de`, para o histórico de preço), que não têm módulo de leitura próprio. O Copilot não escreve no ERP.
- `politica_compra` fala direto com o schema `copilot` do Postgres. Não passa pelo `erp_adapter`, porque a política é dado do Copilot, não do ERP.
- `ai` fala direto com `copilot.trechos_corpus` (pgvector), atrás do port `TrechosRepositorio`, com `copilot.registros_decisao`, atrás do port `RegistrosDecisao`, com a API da TypeSafe, atrás do port `DecisionModel`, e com a Anthropic (Claude), atrás do port `Redator`. No chat, só lê dos outros módulos: `catalog` (lista de SKUs), `ficha_sku` (ficha completa), `purchasing` (só `sugerir_pedido`) e `politica_compra` (política ativa). Nada no `ai` escreve no ERP.
- `ficha_sku` depende de `catalog`, `inventory`, `sales` e não fala com o `erp_adapter` direto.
- `inventory` depende de `sales` (cobertura precisa de giro).
- `catalog`, `inventory`, `sales` e `purchasing` dependem de `erp_adapter`.
- `erp_adapter` importa só os DTOs de domínio (`catalog.schemas`, `inventory.schemas`, `sales.schemas`) para devolvê-los prontos. O DTO dos itens de pedido (`ItemDePedido`) é dele (`erp_adapter/schemas.py`), para o `purchasing` depender do `erp_adapter` sem ciclo. Os serviços desses módulos ele não chama.
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
