# Copilot de Compras

Assistente de decisão de compras para um atacadista de cama, mesa e banho. A ideia final é usar LLM com RAG e tool use sobre dados de um ERP simulado para sugerir o que comprar, quanto, de quem e quando - sempre com humano aprovando. Vocabulário, decisões e restrições de domínio vivem em [`CONTEXT.md`](CONTEXT.md).

> **Sistema em construção.** Esta fatia cobre M0-M4 do [roadmap](.scratch/copilot-compras/roadmap.md): fundação técnica, ERP fake com seed, primeira leitura útil de SKU (giro, cobertura, sazonalidade, fornecedores), sugestão de pedido determinística com política de compra configurável e busca no corpus de documentos com o filtro do Jev (`/rag/busca`). Ainda não há chat nem LLM redigindo respostas (M5). Próximos passos: ver `.scratch/copilot-compras/roadmap.md`.

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
```

A ingestão baixa o modelo de embedding para `.cache/fastembed` na primeira vez. A `/rag/busca` também precisa da `JEV_KEY` (chave da API da TypeSafe) no `.env`: copie o `.env.example` e preencha. Sem a chave, só a busca responde 503.

O app fica em `http://localhost:8000`. Confirme com:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok"}
```

## Variáveis de ambiente

Todas têm padrão, menos a `JEV_KEY`, e podem vir do `.env` na raiz (veja o `.env.example`).

| Variável | Padrão | Para quê |
| -------- | ------ | -------- |
| `DATABASE_URL` | `postgresql+psycopg://copilot:copilot@localhost:5432/copilot` | Conexão com o Postgres. |
| `JEV_KEY` | vazio | Chave da API da TypeSafe. Sem ela, `/rag/busca` responde 503 e os testes `externo` são pulados. |
| `JEV_MODEL` | `jev-1.13.0` | Versão fixa do Jev. Os limiares da busca foram calibrados nela. |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embedding local (fastembed, 384 dimensões). |
| `CORPUS_DIR` | `corpus` | Pasta que `scripts.ingerir_corpus` lê. |
| `FASTEMBED_CACHE_PATH` | `.cache/fastembed` | Onde o modelo de embedding fica em cache. |

## Testes

Os testes se dividem em três categorias:

- **Unitários e de integração leve** (padrão) - não dependem do Postgres. Usam os adapters em memória (`InMemoryERPAdapter`, `InMemoryDecisionModel`, `FakeEmbedder`).
- **Smoke end-to-end** (`tests/smoke/`) - sobem o app real contra o Postgres real com seed populado e o corpus ingerido com o embedding de verdade.
- **Externos** (marcador `externo`) - chamam o Jev real, com custo desprezível. São pulados sem `JEV_KEY`.

```bash
# Só unitários (rápido, offline)
uv run pytest -m "not smoke and not externo"

# Só smoke end-to-end (requer docker compose up; aplica migrations, seed e ingestão
# do corpus sozinho, o que apaga e recria os dados do schema erp no banco local)
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
| `GET` | `/skus/{sku_code}/analise` | Análise composta: nome, categoria, estoque, giro, cobertura, fornecedores. |
| `GET` | `/skus/abaixo-do-piso?dias=20` | SKUs com cobertura abaixo do piso de alerta. Sem `dias`, usa o `piso_alerta_dias` da política ativa. |
| `GET` | `/skus/{sku_code}/sugestao-compra` | Sugestão de pedido: quantidade, fornecedor, valor, memória de cálculo e alertas. |
| `GET` | `/skus/{sku_code}/vendas?meses=12` | Série mensal de vendas. |
| `GET` | `/skus/{sku_code}/sazonalidade` | Multiplicadores mês-a-mês (1 = neutro). |
| `GET` | `/skus/{sku_code}/fornecedores` | Preço, MOQ e lead time por fornecedor. |
| `GET` | `/politica-compra` | Política de compra ativa (`versao`, `criada_em`, `parametros`). |
| `PUT` | `/politica-compra` | Recebe os parâmetros completos, valida e grava uma versão nova (201, ou 422 se inválida). |
| `GET` | `/rag/busca?q=...&k=30` | Trechos do corpus mais parecidos com a pergunta, classificados pelo filtro do Jev, e os conflitos entre eles. |

`sku_code` é o código legível do SKU (ex.: `CB-AZUL-CASAL-05`), não o UUID.

Unidades monetárias: `preco_unitario_reais` vem em **centavos** (`7488` = R$ 74,88), enquanto `pedido_minimo_reais` vem em **reais inteiros** (`25000` = R$ 25.000). `valor_estimado_centavos` vem em centavos.

### Exemplo: `GET /skus/CB-AZUL-CASAL-05/analise`

```json
{
  "sku_code": "CB-AZUL-CASAL-05",
  "produto_nome": "Colcha Bouti",
  "categoria": "jogo_cama",
  "estoque": {
    "quantidade_disponivel": 90,
    "quantidade_reservada": 11,
    "atualizado_em": "2026-09-01T00:00:00Z"
  },
  "giro": {
    "unidades_por_mes": 32.0,
    "meses_considerados": 6
  },
  "cobertura": {
    "meses": 2.8125,
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
  "quantidade": 85,
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
  "valor_estimado_centavos": 791945,
  "calculo": {
    "giro_mensal": 52.333333333333336,
    "disponivel": 81,
    "em_transito": 56,
    "posicao": 137,
    "lead_time_dias": 67,
    "lead_time_origem": "observado",
    "estoque_na_chegada": 20.12222222222222,
    "qtd_necessaria": 85,
    "cobertura_na_chegada_meses": 2.008704883227176
  },
  "alertas": [
    {
      "tipo": "abaixo_pedido_minimo",
      "mensagem": "O pedido de R$ 7.919,45 fica abaixo do pedido mínimo de R$ 25.000,00 do fornecedor Verdela Home. Junte com outros SKUs dele."
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

O mecanismo da sugestão (contar o que está em trânsito, descontar o consumo durante o lead time, respeitar o MOQ, nunca esconder violação de teto) é fixo no código. Os parâmetros de estratégia (teto, pisos, ciclo de compra, qual lead time usar, critério de fornecedor, sazonalidade, regra de SKU novo) são do comprador chefe e ficam na política de compra, versionada em `copilot.politicas_compra`. Cada `PUT /politica-compra` cria uma versão nova, e a ativa é a de maior `versao`. A v1 nasce na migration com os valores da política v3 do corpus.

A justificativa está em [`docs/adr/0003-politica-de-compra-configuravel.md`](docs/adr/0003-politica-de-compra-configuravel.md). Os parâmetros sem base na política v3 são chutes até o comprador responder [`.scratch/sugestao-compra/perguntas-comprador.md`](.scratch/sugestao-compra/perguntas-comprador.md). As respostas viram um `PUT /politica-compra`, sem mudança de código.

### Busca no corpus: `GET /rag/busca`

A busca recupera os `k` trechos mais parecidos com `q` (padrão 30, de 1 a 40) e faz ao Jev quatro perguntas sobre cada um: se é relevante para a pergunta, se tem evidência que responde a ela, se contradiz algo que a pergunta dá como certo e se tenta dar instruções ao sistema. Quem classifica é o código, com os limiares de `LIMIARES` em `src/ai/busca.py`, nesta ordem:

1. tenta dar instruções: `descartado` (`injecao`)
2. contradiz a premissa da pergunta: `conflitante`
3. não é relevante: `descartado` (`irrelevante`)
4. tem evidência: `aceito`
5. senão: `descartado` (`sem_evidencia`)

Depois, o Jev compara dois a dois os aceitos e conflitantes de documentos diferentes, entre os 6 mais parecidos. Os pares que afirmam coisas incompatíveis sobre o mesmo fato vão para `conflitos`. A busca só sinaliza: não escolhe o lado certo nem compara datas.

A resposta traz também os `descartado`, de propósito, para auditar o filtro. Se o Jev estiver fora do ar ou faltar a `JEV_KEY`, a resposta é 503. A busca nunca sai sem o filtro. Com o corpus ainda não ingerido, a resposta é 200 com as listas vazias.

Exemplo de `GET /rag/busca?q=lead time da Katrina`, cortado para 3 dos 30 trechos e 1 dos 6 conflitos:

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
      "tags": ["fornecedor-principal", "felpudo", "cama", "sc"],
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
      "id": "contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato",
      "documento": "contratos/contrato-katrina-2025.md",
      "titulo": "Contrato de Fornecimento Anual - Katrina Têxtil x Atacadista > Notas internas (não fazem parte do contrato)",
      "tipo": "contrato",
      "data": "2025-01-20",
      "tags": ["katrina", "vigencia-2025", "felpudo"],
      "texto": "Contrato de Fornecimento Anual - Katrina Têxtil x Atacadista > Notas internas (não fazem parte do contrato)\n\n- O mínimo de R$ 240k/semestre é apertado - em 2024 batemos R$ 265k no primeiro sem e R$ 210k no segundo. Segundo semestre 2024 caiu porque atrasamos pedido de Natal em 3 semanas.\n- Cláusula 3 (antecedência de 45 dias) é rigorosamente cumprida pela Katrina em setembro-outubro.\n- Teto de reajuste (8%) foi acionado em 2023 - fórmula deu 11%, negociamos pra 7.5%.",
      "similaridade": 0.6557603571800253,
      "classificacao": "aceito",
      "motivo_descarte": null,
      "avaliacao": {
        "relevante": 0.9,
        "tem_evidencia": 0.91,
        "contradiz_premissa": 0.11,
        "tenta_instruir": 0.03
      }
    },
    {
      "id": "fornecedores/katrina-textil.md#contato-comercial",
      "documento": "fornecedores/katrina-textil.md",
      "titulo": "Katrina Têxtil S.A. > Contato comercial",
      "tipo": "fornecedor",
      "data": "2025-11-10",
      "tags": ["fornecedor-principal", "felpudo", "cama", "sc"],
      "texto": "Katrina Têxtil S.A. > Contato comercial\n\nRepresentante: [placeholder] - reuniões trimestrais presenciais ou por vídeo.",
      "similaridade": 0.61969659792914,
      "classificacao": "descartado",
      "motivo_descarte": "irrelevante",
      "avaliacao": {
        "relevante": 0.11,
        "tem_evidencia": 0.04,
        "contradiz_premissa": 0.08,
        "tenta_instruir": 0.02
      }
    }
  ],
  "conflitos": [
    {
      "trecho_a": "fornecedores/katrina-textil.md#lead-time",
      "trecho_b": "contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato",
      "probabilidade": 0.33
    }
  ]
}
```

`trechos` vem com os aceitos primeiro, depois os conflitantes e os descartados, e dentro de cada grupo pela similaridade. `trecho_a` é o trecho do par mais parecido com a pergunta.

O papel do Jev (ele responde, o código decide) está na [ADR-0002](docs/adr/0002-jev-decide-codigo-executa-llm-redige.md), e o embedding local, na [ADR-0004](docs/adr/0004-embeddings-locais.md). As perguntas, os limiares e o que o spike mediu estão em [`.scratch/rag-jev/spike-resultado.md`](.scratch/rag-jev/spike-resultado.md). O gate da ADR-0002 não passou na relevância, e o dev manteve a ADR aceitando o risco: a busca prefere deixar passar trecho irrelevante a perder trecho relevante.

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
├── purchasing/       sugestão de pedido (quanto, de quem, memória de cálculo, alertas)
├── ai/               corpus em trechos, ingestão no pgvector, busca com o filtro do Jev
├── api/              camada HTTP (FastAPI routers, DTOs de resposta)
├── db/               config, engine, health-check
└── main.py           bootstrap FastAPI

scripts/              seed.py, ingerir_corpus.py, spike_jev.py, avaliar_recuperacao.py, jev_check.py, db-init (extensões Postgres)
corpus/               documentos do RAG (markdown com frontmatter)
evals/                casos rotulados e respostas cruas do spike do Jev
alembic/              migrations versionadas
tests/                fakes.py + testes cross-módulo + tests/smoke/ end-to-end
```

Grafo de dependência (setas: "depende de"):

```
                      +-----+
                      | api |
                      +-----+
                         |
          +--------------+--------------------------------+
          |              v                                v
          |       +------------+                        +----+     +----------------+
          |       | purchasing |                        | ai |---->| Jev (TypeSafe) |
          |       +------------+                        +----+     +----------------+
          |              |                                |
          +--------------+-----------------+              |
          v                                v              |
    +-----------+                  +-----------------+    |
    | ficha_sku |                  | politica_compra |    |
    +-----------+                  +-----------------+    |
          |                                |              |
     +----+--------+-------------+         |              |
     v             v             v         |              |
+---------+  +-----------+  +-------+      |              |
| catalog |  | inventory |->| sales |      |              |
+---------+  +-----------+  +-------+      |              |
     |             |             |         |              |
     +-------------+-------------+         |              |
                   v                       |              |
            +-------------+                |              |
            | erp_adapter |                |              |
            +-------------+                |              |
                   |                       |              |
                   v                       v              v
        +-----------------------------------------------------+
        |           Postgres (schemas erp e copilot)          |
        +-----------------------------------------------------+
```

O grafo mostra só as arestas principais. As chamadas diretas de `api` e `purchasing` para os módulos de baixo estão na lista:

- `api` depende de `purchasing` (para `/sugestao-compra`), `ficha_sku` (para `/analise`), `politica_compra` (para `/politica-compra` e o piso padrão de `/abaixo-do-piso`) e `ai` (para `/rag/busca`), e chama `catalog`, `inventory`, `sales` direto nos endpoints de leitura simples.
- `purchasing` depende de `ficha_sku`, `inventory`, `sales` e `politica_compra`, e importa o DTO `FornecedorParaSKU` de `catalog.schemas`. Nunca fala com o `erp_adapter` direto.
- `politica_compra` fala direto com o schema `copilot` do Postgres. Não passa pelo `erp_adapter`, porque a política é dado do Copilot, não do ERP.
- `ai` fala direto com `copilot.trechos_corpus` (pgvector), atrás do port `TrechosRepositorio`, e com a API da TypeSafe, atrás do port `DecisionModel`. Por enquanto não chama nenhum outro módulo.
- `ficha_sku` depende de `catalog`, `inventory`, `sales` e não fala com o `erp_adapter` direto.
- `inventory` depende de `sales` (cobertura precisa de giro).
- `catalog`, `inventory`, `sales` dependem de `erp_adapter`.
- `erp_adapter` importa só os DTOs de domínio (`catalog.schemas`, `inventory.schemas`, `sales.schemas`) para devolvê-los prontos. Os serviços desses módulos ele não chama.
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
