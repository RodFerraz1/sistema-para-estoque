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

# Só smoke (requer docker compose up + alembic upgrade head)
uv run pytest tests/smoke/
# ou, equivalente, por marker (cobre também tests/test_seed_smoke.py):
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

`sku_code` é o código legível do SKU (ex.: `TBC-BEG-70140`), não o UUID.

### Exemplo: `GET /skus/TBC-BEG-70140/analise`

```json
{
  "sku_code": "TBC-BEG-70140",
  "produto_nome": "Toalha Banho Conforto",
  "categoria": "felpudo",
  "estoque": {
    "quantidade_disponivel": 120,
    "quantidade_reservada": 10,
    "atualizado_em": "2026-09-01T00:00:00Z"
  },
  "giro": {
    "unidades_por_mes": 30.0,
    "meses_considerados": 6
  },
  "cobertura": {
    "meses": 4.0,
    "sem_giro": false
  },
  "fornecedores": [
    {
      "fornecedor_id": "5f3c1d8a-4b2e-5c9d-8f1a-9e2c7b6d4a01",
      "fornecedor_nome": "Katrina Têxtil",
      "preco_unitario_reais": 1800,
      "moq_unidades": 48,
      "lead_time_dias_contratado": 35,
      "lead_time_dias_observado": 38,
      "prazo_pagamento_padrao": "30/60",
      "pedido_minimo_reais": 10000
    }
  ]
}
```

A documentação interativa (OpenAPI) fica em `http://localhost:8000/docs`.

## Estrutura de módulos

Árvore de código:

```
src/
├── erp_adapter/   Port + PostgresERPAdapter + InMemoryERPAdapter (única fronteira com o ERP)
├── catalog/       SKU, produto, fornecedor
├── inventory/     estoque atual, cobertura, movimentações, abaixo do piso
├── sales/         giro médio, histórico de vendas, sazonalidade
├── api/           camada HTTP (FastAPI routers, DTOs de resposta)
├── db/            engine, session, health-check
└── main.py        bootstrap FastAPI

scripts/           seed.py + db-init (extensões Postgres)
alembic/           migrations versionadas
tests/             fakes.py + testes cross-módulo + tests/smoke/ end-to-end
```

Grafo de dependência (setas: "depende de"):

```
                    +-----+
                    | api |
                    +-----+
                    /  |  \
                   v   v   v
             +---------+  +-----------+  +-------+
             | catalog |  | inventory |  | sales |
             +---------+  +-----------+  +-------+
                    \        |           /
                     \       v          /
                      \  +-------+     /
                       ->| sales |<---
                         +-------+
                             |
                             v
                       +-------------+
                       | erp_adapter |
                       +-------------+
                             |
                             v
                       +-----------+
                       | Postgres  |
                       +-----------+
```

- `api` depende de `catalog`, `inventory`, `sales`.
- `catalog`, `inventory`, `sales` dependem de `erp_adapter`.
- `inventory` depende de `sales` (cobertura precisa de giro).
- Nenhum outro caminho é permitido: `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

A justificativa da organização por domínio (e não por camada técnica) e a política de fronteiras entre módulos estão em [`docs/adr/0001-monolito-modular-por-dominio.md`](docs/adr/0001-monolito-modular-por-dominio.md).
