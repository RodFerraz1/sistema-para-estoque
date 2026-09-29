# Copilot de Compras

Assistente de decisão de compras para um atacadista de cama, mesa e banho. A ideia final é usar LLM com RAG e tool use sobre dados de um ERP simulado para sugerir o que comprar, quanto, de quem e quando - sempre com humano aprovando. Vocabulário, decisões e restrições de domínio vivem em [`CONTEXT.md`](CONTEXT.md).

> **Sistema em construção.** Esta fatia cobre M0-M2 do [roadmap](.scratch/copilot-compras/roadmap.md): fundação técnica, ERP fake com seed e primeira leitura útil de SKU (giro, cobertura, sazonalidade, fornecedores). Os módulos `purchasing` e `ai` **ainda não existem**, e o corpus RAG (`.scratch/copilot-compras/rag-seeds/`) está guardado mas **não é usado**. Próximos passos: ver `.scratch/copilot-compras/roadmap.md`.

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
| `GET` | `/skus/abaixo-do-piso?dias=20` | SKUs com cobertura abaixo do piso (padrão 20 dias). |
| `GET` | `/skus/{sku_code}/vendas?meses=12` | Série mensal de vendas. |
| `GET` | `/skus/{sku_code}/sazonalidade` | Multiplicadores mês-a-mês (1 = neutro). |
| `GET` | `/skus/{sku_code}/fornecedores` | Preço, MOQ e lead time por fornecedor. |

`sku_code` é o código legível do SKU (ex.: `CB-AZUL-CASAL-05`), não o UUID.

Unidades monetárias: `preco_unitario_reais` vem em **centavos** (`7488` = R$ 74,88), enquanto `pedido_minimo_reais` vem em **reais inteiros** (`25000` = R$ 25.000).

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

A documentação interativa (OpenAPI) fica em `http://localhost:8000/docs`.

## Estrutura de módulos

Árvore de código:

```
src/
├── erp_adapter/   Port + PostgresERPAdapter + InMemoryERPAdapter (única fronteira com o ERP)
├── catalog/       SKU, produto, fornecedor
├── inventory/     estoque atual, cobertura, abaixo do piso
├── sales/         giro médio, histórico de vendas, sazonalidade
├── ficha_sku/     compõe a ficha completa de um SKU (usada por /analise)
├── api/           camada HTTP (FastAPI routers, DTOs de resposta)
├── db/            config, engine, health-check
└── main.py        bootstrap FastAPI

scripts/           seed.py, jev_check.py, db-init (extensões Postgres)
alembic/           migrations versionadas
tests/             fakes.py + testes cross-módulo + tests/smoke/ end-to-end
```

Grafo de dependência (setas: "depende de"):

```
                +-----+
                | api |
                +-----+
                   |
                   v
             +-----------+
             | ficha_sku |
             +-----------+
                   |
     +-------------+-------------+
     v             v             v
+---------+  +-----------+  +-------+
| catalog |  | inventory |->| sales |
+---------+  +-----------+  +-------+
     |             |             |
     +-------------+-------------+
                   v
            +-------------+
            | erp_adapter |
            +-------------+
                   |
                   v
             +----------+
             | Postgres |
             +----------+
```

- `api` depende de `ficha_sku` (para `/analise`) e chama `catalog`, `inventory`, `sales` direto nos endpoints de leitura simples.
- `ficha_sku` depende de `catalog`, `inventory`, `sales` e não fala com o `erp_adapter` direto.
- `inventory` depende de `sales` (cobertura precisa de giro).
- `catalog`, `inventory`, `sales` dependem de `erp_adapter`.
- `erp_adapter` importa só os DTOs de domínio (`catalog.schemas`, `inventory.schemas`, `sales.schemas`) para devolvê-los prontos. Os serviços desses módulos ele não chama.
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
