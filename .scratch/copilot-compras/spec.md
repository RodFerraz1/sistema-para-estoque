---
Status: ready-for-agent
Escopo: M0-M2 do roadmap (fundação + ERP fake + primeira leitura útil de SKU)
Vocabulário: ver /CONTEXT.md
Decisão arquitetural base: ver /docs/adr/0001-monolito-modular-por-dominio.md
---

# Spec 01 - Fundação técnica e primeira leitura do ERP fake

## Problem Statement

O comprador chefe do atacadista precisa decidir compras a partir de dados de estoque, giro e histórico de vendas do ERP. Hoje esse dado está no Maos (ERP proprietário), sem integração acessível. Não existe nenhuma ferramenta ou aplicação onde essa informação seja consolidada por SKU num formato pronto pra suportar decisão - qualquer consulta hoje passa por análise manual planilha-a-planilha.

O objetivo desta fatia é ter a base sobre a qual o Copilot vai operar: um ERP fake com dados sintéticos plausíveis (2 anos de vendas com sazonalidade, catálogo, fornecedores, estoque) e uma API que expõe a foto atual de um SKU em conceitos de domínio (estoque atual, giro médio, cobertura em meses).

Este spec **não** cobre sugestão de compra (M3) nem qualquer componente de IA (M4+). É pré-requisito de tudo.

## Solution

Uma aplicação Python (FastAPI) que:

1. Roda localmente via `docker compose up` (app + Postgres com pgvector).
2. Popula um ERP fake com dados sintéticos reprodutíveis via script `seed.py`.
3. Expõe endpoints HTTP que retornam informação de SKU em vocabulário de domínio (não em vocabulário de tabela do banco).
4. Estrutura o código em módulos com fronteiras explícitas (`erp_adapter`, `catalog`, `inventory`, `sales`), preparado pra crescer nos próximos specs sem refatoração das fronteiras.

## User Stories

### Usuário-final (comprador chefe)

1. Como comprador chefe, quero consultar um SKU pelo código e receber seu nome, categoria e status atual, para localizar rapidamente o item.
2. Como comprador chefe, quero ver o estoque atual (disponível e reservado) de um SKU, para saber quanto ainda tenho.
3. Como comprador chefe, quero ver o giro médio mensal de um SKU (média dos últimos 6 meses), para saber a velocidade de venda.
4. Como comprador chefe, quero ver a cobertura em meses de um SKU (estoque atual dividido pelo giro), para saber quanto tempo o estoque atende.
5. Como comprador chefe, quero ver o histórico de vendas mensais de um SKU nos últimos 12 meses, para entender tendência.
6. Como comprador chefe, quero ver a sazonalidade de um SKU (multiplicadores mês-a-mês), para ajustar decisões.
7. Como comprador chefe, quero ver todos os fornecedores que suprem um SKU com suas condições (preço, MOQ, lead time contratado e observado), para escolher onde comprar.
8. Como comprador chefe, quero listar SKUs abaixo do piso de estoque (menos de 20 dias de cobertura), para priorizar reposição.
9. Como comprador chefe, quero que os SKUs sejam identificados pelo `sku_code` legível (ex: `TBC-BEG-70140`), não por UUID, para poder digitar e memorizar.

### Desenvolvedor

10. Como desenvolvedor, quero subir o sistema inteiro com `docker compose up` num único comando, para iterar rápido.
11. Como desenvolvedor, quero um endpoint `/health` que retorne 200 quando o app e o banco estão saudáveis, para confirmar deploy.
12. Como desenvolvedor, quero um script `seed.py` que popule o banco com dados sintéticos reprodutíveis (mesmo seed → mesmos dados), para testes determinísticos.
13. Como desenvolvedor, quero migrations versionadas com Alembic, para evoluir o schema com histórico.
14. Como desenvolvedor, quero interfaces de módulo tipadas com Pydantic, para pegar erros de contrato cedo.
15. Como desenvolvedor, quero que módulos não acessem tabelas de outros módulos, para manter fronteiras claras (ADR-0001).
16. Como desenvolvedor, quero poder trocar a implementação do `erp_adapter` (Postgres → real, ou → mock em testes) sem tocar em nenhum outro módulo, para preservar o padrão Ports & Adapters.
17. Como desenvolvedor, quero um `InMemoryERPAdapter` disponível para testes dos módulos superiores, para não depender de banco em teste unitário.
18. Como desenvolvedor, quero um README com "como rodar localmente" e diagrama simples de módulos, para retomar o projeto após pausa.

## Implementation Decisions

### Stack

- Linguagem: **Python 3.12+**.
- Gerenciador de pacotes/venv: **`uv`** (rápido, moderno, resolvedor de dependências correto).
- Framework HTTP: **FastAPI** (Pydantic nativo, docs automáticas).
- ORM: **SQLAlchemy 2.x** (estilo `Mapped[...]`, tipagem forte).
- Migrations: **Alembic**.
- Testes: **pytest** + **pytest-asyncio**.
- Container: **Docker + docker compose**. Postgres 16 + extensão `pgvector` (pgvector já entra agora mesmo sem uso em M0-M2 pra evitar migration futura só pra isso).

Vocabulário: código, tabelas, DTOs, endpoints e mensagens de log usam **termos do `CONTEXT.md`** (SKU, Fornecedor, Giro, Cobertura, etc). Traduções pra inglês em código só quando obrigatório por convenção da linguagem (nomes de variáveis técnicas). Nomes de conceitos de domínio ficam em português.

### Estrutura de banco

- Um único Postgres físico, dois schemas: **`erp`** (para todas as tabelas do ERP fake) e **`copilot`** (para dados do próprio app - vazio em M0-M2, criado por antecipação).
- Tabelas do schema `erp`: definidas em `.scratch/copilot-compras/erp-schema.md`. As 9 tabelas entram nesta fatia.
- Movimentações de estoque são **append-only** (ledger). `estoque_snapshot` é fotografia recalculável.
- Quantidades sempre inteiras positivas (unidades de SKU). Valores monetários em centavos (inteiros).

### Módulos e dependências

Estrutura de código:

```
src/
├── erp_adapter/       # Port + implementação Postgres
├── catalog/           # SKU, produto, fornecedor
├── inventory/         # estoque, cobertura, movimentações
├── sales/             # giro, vendas, sazonalidade, previsão simples
├── api/               # camada HTTP (FastAPI routes)
├── db/                # engine, session, base
└── main.py            # bootstrap FastAPI
```

Módulos `purchasing` e `ai` **não são criados** nesta fatia.

Cada módulo tem:
- `schemas.py`: DTOs Pydantic (interface pública tipada).
- `service.py` (ou arquivo com nome do módulo): implementação da interface.
- `tests/`: testes unitários que usam `InMemoryERPAdapter` quando aplicável.

Dependências permitidas (grafo):
- `catalog`, `inventory`, `sales` → `erp_adapter`
- `inventory` → `sales` (para cobertura, que precisa de giro)
- `api` → `catalog`, `inventory`, `sales`

**Nenhum outro caminho é permitido.** `catalog` não chama `inventory`, `sales` não chama `catalog`, etc.

### Interfaces expostas nesta fatia

Do `.scratch/copilot-compras/module-interfaces.md`, apenas o subconjunto para M0-M2:

- `ERPAdapter.get_sku_raw`, `list_skus_raw`, `get_fornecedor_raw`, `list_fornecedores_para_sku`, `get_estoque_atual`, `list_movimentacoes`, `list_vendas`.
- `Catalog.get_sku`, `buscar_sku_por_codigo`, `list_fornecedores_para_sku`.
- `Inventory.estoque_atual`, `cobertura_meses`, `historico_movimentacoes`, `abaixo_do_piso`.
- `Sales.giro_medio_mensal`, `historico_vendas`, `sazonalidade`.

Métodos de escrita (`criar_pedido_compra`, `submeter_pedido`) ficam fora - não há pedido nesta fatia.

### Endpoints HTTP

- `GET /health` → `{"status": "ok", "db": "ok"}`.
- `GET /skus/{sku_code}/analise` → objeto composto com nome do SKU, estoque atual, giro médio, cobertura em meses, fornecedores disponíveis. `sku_code` é o código legível, não o UUID.
- `GET /skus/abaixo-do-piso?dias=20` → lista de SKUs com cobertura abaixo do piso.
- `GET /skus/{sku_code}/vendas?meses=12` → série mensal de vendas.
- `GET /skus/{sku_code}/sazonalidade` → multiplicadores mês-a-mês.
- `GET /skus/{sku_code}/fornecedores` → lista com preço, MOQ, lead time contratado e observado.

Todas as respostas são JSON. Erros seguem padrão FastAPI (`HTTPException` com status apropriado). Sem autenticação nesta fatia.

### Ports & Adapters em `erp_adapter`

- `erp_adapter/port.py`: `class ERPAdapter(Protocol)` com todas as assinaturas.
- `erp_adapter/postgres.py`: `PostgresERPAdapter` que implementa o Protocol via SQLAlchemy.
- `erp_adapter/in_memory.py`: `InMemoryERPAdapter` que implementa o Protocol via dict/list, apenas para testes.
- Injeção de dependência via FastAPI `Depends`; em teste, sobrescreve pela versão in-memory.

### Seed de dados

Script `scripts/seed.py`, executável via `uv run python -m scripts.seed`:

- Semente fixa (`random.seed(42)`) para reprodutibilidade.
- ~15 produtos distribuídos nas categorias `felpudo`, `jogo_cama`, `mesa`, `cozinha`.
- ~80 SKUs (variações de cor/tamanho/gramatura).
- 5 fornecedores (3 já descritos em `corpus/fornecedores/` + 2 secundários).
- ~180 relações fornecedor-SKU com preços plausíveis.
- Estoque snapshot coerente com cobertura entre 0.5 e 4 meses (variedade de casos).
- 2 anos (24 meses) de movimentações e vendas com padrão sazonal (spike em novembro-dezembro pro Natal, bump em maio pro dia das mães, dip em fevereiro-março).
- 15 pedidos de compra em estados variados (`recebido_total`, `enviado`, `rascunho`).

O seed deve ser **idempotente**: rodar duas vezes não duplica dados (limpa e repopula).

### Cálculos de domínio

- **`giro_medio_mensal`**: soma vendas dos últimos 6 meses fechados, divide por 6. Se SKU tem menos de 6 meses de histórico, usa o que tem (nunca extrapola).
- **`cobertura_meses`**: `estoque_atual.disponivel / giro_medio_mensal`. Se giro = 0, retorna `float('inf')` (ou representação semântica de "sem giro").
- **`sazonalidade`**: para cada mês do ano (1-12), calcula `média das vendas naquele mês nos últimos 24 meses / média geral do período`. Retorna dict {mes: multiplicador}.
- **`abaixo_do_piso(dias_piso)`**: converte piso em meses (`dias_piso / 30`), retorna SKUs com cobertura abaixo desse limite. Padrão `dias_piso=20`.

## Testing Decisions

### Filosofia

Testes exercitam **comportamento externo** dos módulos, não implementação. Um teste que precise mockar interna de um módulo é sinal de fronteira errada.

### Que teste vive onde

- **`erp_adapter/tests/`**: testes de integração contra Postgres real (via container em teste ou fixture com banco de teste). Cobrem a implementação `PostgresERPAdapter` executando queries reais.
- **`catalog/tests/`, `inventory/tests/`, `sales/tests/`**: testes unitários que injetam `InMemoryERPAdapter`. Cobrem a lógica de domínio de cada módulo sem depender de banco.
- **`api/tests/`**: testes de integração da camada HTTP, subindo o app FastAPI com `InMemoryERPAdapter` injetado. Testa contratos de endpoint.
- **Testes end-to-end**: um único teste "smoke" que roda com Postgres real + seed + chama todos os endpoints e verifica shape das respostas.

### Prior art

Sem prior art no repositório - este é o começo. Convenções ficam definidas neste spec.

### Cobertura mínima antes de considerar a fatia pronta

- Cada método público de `Catalog`, `Inventory`, `Sales` tem pelo menos um teste feliz e um edge case (SKU inexistente, SKU sem vendas, giro zero, etc).
- `PostgresERPAdapter` tem pelo menos um teste por método público contra banco real.
- Todos os endpoints têm pelo menos um teste de status code + shape do JSON.

## Out of Scope

- **Módulos `purchasing` e `ai`**: viram specs próprios (spec 02 e spec 03).
- **Sugestão de compra**: sem lógica de decisão de "quanto comprar". Apenas leitura.
- **Qualquer componente de LLM ou RAG**: nem cliente, nem embedding, nem chat.
- **Interface visual (UI)**: apenas HTTP + JSON nesta fatia. UI vai junto com M7.
- **Autenticação, autorização, multi-usuário**.
- **Múltiplos CDs / localização física de estoque**.
- **Devoluções ao fornecedor** (não modelado no schema).
- **Notas fiscais, impostos, tributação**.
- **Cliente do atacadista como entidade** (permanece como string opaca `cliente_ref` em `vendas`).
- **Deploy remoto**. Roda só localmente. Deploy é decisão de M8.
- **Atualização de estoque em tempo real**. Estoque só muda via seed nesta fatia (não há endpoint que altere).
- **Auditoria de mudanças em dados mestres**.

## Further Notes

- Toda decisão sobre schema está em `.scratch/copilot-compras/erp-schema.md`. Se surgir tensão entre este spec e aquele documento, o schema doc é a referência - e neste caso um ADR é obrigatório antes de mudar.
- Toda decisão sobre interfaces de módulo está em `.scratch/copilot-compras/module-interfaces.md`. Mesmo princípio.
- Roadmap completo em `.scratch/copilot-compras/roadmap.md`. Este spec cobre M0, M1 e M2.
- Corpus de documentos sintéticos (`corpus/`) existe mas **não é usado** nesta fatia. Fica pra spec 03 (RAG).
- O sistema é single-user por design (só o comprador chefe). Não vale investir em multi-user antes de M8.
- Os nomes de fornecedores no seed devem coincidir com os do corpus RAG (Katrina Têxtil, Verdela Home, Malha Fina) para que specs futuras já encontrem consistência entre dado estruturado e documento não-estruturado.
