# Copilot de Compras

Assistente de decisão de compras para um atacadista de cama, mesa e banho. A ideia final é usar LLM com RAG e tool use sobre dados de um ERP simulado para sugerir o que comprar, quanto, de quem e quando - sempre com humano aprovando. Vocabulário, decisões e restrições de domínio vivem em [`CONTEXT.md`](CONTEXT.md).

> **Sistema em construção.** Esta fatia cobre M0-M3 do [roadmap](.scratch/copilot-compras/roadmap.md): fundação técnica, ERP fake com seed, primeira leitura útil de SKU (giro, cobertura, sazonalidade, fornecedores) e sugestão de pedido determinística com política de compra configurável. O módulo `ai` **ainda não existe**, e o corpus RAG (`.scratch/copilot-compras/rag-seeds/`) está guardado mas **não é usado**. Próximos passos: ver `.scratch/copilot-compras/roadmap.md`.

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
```

O app fica em `http://localhost:8000`. Confirme com:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"ok"}
```

## Testes

Os testes se dividem em duas categorias:

- **Unitários e de integração leve** (padrão) - não dependem do Postgres. Usam `InMemoryERPAdapter`.
- **Smoke end-to-end** (`tests/smoke/`) - sobem o app real contra o Postgres real com seed populado.

```bash
# Só unitários (rápido, offline)
uv run pytest -m "not smoke"

# Só smoke end-to-end (requer docker compose up; aplica migrations e seed sozinho,
# o que apaga e recria os dados do schema erp no banco local)
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
├── api/              camada HTTP (FastAPI routers, DTOs de resposta)
├── db/               config, engine, health-check
└── main.py           bootstrap FastAPI

scripts/              seed.py, jev_check.py, db-init (extensões Postgres)
alembic/              migrations versionadas
tests/                fakes.py + testes cross-módulo + tests/smoke/ end-to-end
```

Grafo de dependência (setas: "depende de"):

```
                      +-----+
                      | api |
                      +-----+
                         |
          +--------------+
          |              v
          |       +------------+
          |       | purchasing |
          |       +------------+
          |              |
          +--------------+-----------------+
          v                                v
    +-----------+                  +-----------------+
    | ficha_sku |                  | politica_compra |
    +-----------+                  +-----------------+
          |                                |
     +----+--------+-------------+         |
     v             v             v         |
+---------+  +-----------+  +-------+      |
| catalog |  | inventory |->| sales |      |
+---------+  +-----------+  +-------+      |
     |             |             |         |
     +-------------+-------------+         |
                   v                       |
            +-------------+                |
            | erp_adapter |                |
            +-------------+                |
                   |                       |
                   v                       v
        +---------------------------------------+
        |    Postgres (schemas erp e copilot)   |
        +---------------------------------------+
```

O grafo mostra só as arestas principais. As chamadas diretas de `api` e `purchasing` para os módulos de baixo estão na lista:

- `api` depende de `purchasing` (para `/sugestao-compra`), `ficha_sku` (para `/analise`) e `politica_compra` (para `/politica-compra` e o piso padrão de `/abaixo-do-piso`), e chama `catalog`, `inventory`, `sales` direto nos endpoints de leitura simples.
- `purchasing` depende de `ficha_sku`, `inventory`, `sales` e `politica_compra`, e importa o DTO `FornecedorParaSKU` de `catalog.schemas`. Nunca fala com o `erp_adapter` direto.
- `politica_compra` fala direto com o schema `copilot` do Postgres. Não passa pelo `erp_adapter`, porque a política é dado do Copilot, não do ERP.
- `ficha_sku` depende de `catalog`, `inventory`, `sales` e não fala com o `erp_adapter` direto.
- `inventory` depende de `sales` (cobertura precisa de giro).
- `catalog`, `inventory`, `sales` dependem de `erp_adapter`.
- `erp_adapter` importa só os DTOs de domínio (`catalog.schemas`, `inventory.schemas`, `sales.schemas`) para devolvê-los prontos. Os serviços desses módulos ele não chama.
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
