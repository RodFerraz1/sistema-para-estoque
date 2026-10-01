---
Status: done
Escopo: refactor arquitetural pós-spec 01 (M0-M2). Não adiciona feature.
Vocabulário: ver /CONTEXT.md
Decisão arquitetural base: ver /docs/adr/0001-monolito-modular-por-dominio.md
Origem: revisão via /improve-codebase-architecture (candidatos 1, 2 e 3)
---

# Spec 02 - Aprofundar `erp_adapter` e extrair módulo `ficha_sku`

## Problem Statement

Terminado o spec 01, o `erp_adapter` ficou **shallow**: 7 métodos que devolvem 7 tipos `*Raw` (SKURaw, FornecedorRaw, EstoqueRaw, etc), cada um espelhando 1:1 uma tabela do schema `erp`. Os módulos `catalog`, `inventory` e `sales` recebem esses `*Raw` e refazem a mesma cópia campo-a-campo em DTOs de domínio (SKU, FornecedorParaSKU, Estoque, etc). O resultado:

- **Escada de 3 DTOs pra cada conceito** (`SKURaw` → `SKU` → `AnaliseSKUResponse`), com código de conversão manual em cada degrau. Uma mudança no schema do ERP obriga tocar 3 arquivos.
- **Filtro e ordenação em Python**: `list_fornecedores_para_sku` puxa todos os fornecedores (inclusive inativos) do banco e ordena por preço em memória. `abaixo_do_piso` puxa todos os SKUs e itera - N+1 queries.
- **Chave de identidade inconsistente**: URLs, seed e vocabulário do domínio usam `sku_code` (`TBC-BEG-70140`), mas o port aceita só UUID. Todo endpoint começa com `catalog.buscar_sku_por_codigo(code)` que puxa TODOS os SKUs e filtra em Python só pra converter código pra UUID.
- **Método morto no port** (`get_fornecedor_raw`) que nenhum caller usa hoje mas provavelmente reaparece em M3.
- **Composição de `/skus/{sku_code}/analise` vive dentro do handler HTTP**: quando M4 (AI) chegar e o agente quiser uma tool `ficha_do_sku(sku_code)`, ele vai ter que fazer um HTTP request pra si mesmo, porque a "ficha completa" só existe encaixada no handler.

Nada disso é bug - todos os testes passam. É fricção arquitetural que vai piorar em cada spec dali pra frente. M3 (`purchasing`) vai empilhar mais métodos no port e mais `*Raw` no schema; M4 (`ai`) vai querer reusar a lógica de composição.

## Solution

Refactor em quatro frentes coordenadas, sem mudar comportamento externo (contrato HTTP idêntico):

1. **Deep `ERPAdapter`**: port passa a falar vocabulário de domínio (`carregar_sku(sku_code)`, `estoque_de(sku_code)`, `vendas_de(sku_code, desde)`, etc), devolve DTOs de domínio direto e absorve filtro/ordenação simples via SQL.
2. **Colapsar a escada de DTOs**: os 7 tipos `*Raw` são deletados. Cada conceito passa a ter só dois DTOs - um de domínio (que vive no módulo que "possui" o conceito) e um de HTTP (que vive em `src/api/schemas.py`). O adapter monta o DTO de domínio direto do banco.
3. **Novo módulo `ficha_sku`**: extrai a composição hoje presa no handler `/analise` pra um módulo próprio (`src/ficha_sku/`), com um método `completa(sku_code) -> Ficha`. Handler HTTP vira 3 linhas: chama o módulo, projeta pra `AnaliseSKUResponse`, retorna.
4. **`InMemoryERPAdapter` acompanha 1:1** o novo `PostgresERPAdapter` - mesma ordenação, mesmo filtro. Divergência entre os dois continua sendo pega pelos smoke tests contra Postgres real.

O `sku_code` (string legível) passa a ser a chave primária pra tudo que envolve SKU no port. `Fornecedor` continua identificado por UUID (schema não tem código legível pra fornecedor).

## User Stories

### Desenvolvedor

1. Como desenvolvedor, quero que o `ERPAdapter` retorne DTOs de domínio (`SKU`, `Estoque`, `Venda`, ...) direto, para eu não precisar escrever `_to_sku()` em cada módulo consumidor.
2. Como desenvolvedor, quero deletar os 7 tipos `*Raw` (`SKURaw`, `FornecedorRaw`, `EstoqueRaw`, `MovimentacaoRaw`, `VendaRaw`, `FornecedorSKURaw`, `FiltrosSKU`), para que uma mudança no schema do ERP toque em 1 arquivo, não 3.
3. Como desenvolvedor, quero que os métodos do port sejam nomeados com verbos de domínio (`carregar_sku`, `fornecedores_de`, `estoque_de`, `vendas_de`, `movimentacoes_de`, `listar_skus`, `carregar_fornecedor`), para que o código leia como discurso do negócio.
4. Como desenvolvedor, quero que `sku_code` seja o parâmetro de entrada dos métodos do port (exceto `carregar_fornecedor`, que continua por UUID por ausência de código de domínio), para que a "dança" `código → UUID → resto` desapareça dos módulos superiores.
5. Como desenvolvedor, quero que o `PostgresERPAdapter` faça filtro de "ativo=true" e ordenação por preço via `WHERE` e `ORDER BY` em SQL (não em Python), para eliminar carga desnecessária ao subir de 80 pra 8000 SKUs.
6. Como desenvolvedor, quero que a lógica de composição de `/skus/{sku_code}/analise` viva num módulo `ficha_sku` reutilizável, para que a futura tool `ficha_do_sku` do agente AI (M4) chame o mesmo código do handler HTTP sem passar por rede.
7. Como desenvolvedor, quero que o handler `/analise` fique com 3 linhas (chamar `ficha_sku.completa`, projetar, retornar), para que a lógica de negócio saia da camada HTTP.
8. Como desenvolvedor, quero que todos os testes existentes continuem valendo (mesmas asserções, comportamento externo idêntico), para que o refactor seja verificável como "zero regressão".
9. Como desenvolvedor, quero que o `InMemoryERPAdapter` continue existindo e sirva os testes unitários dos módulos superiores, para não depender de docker/Postgres em teste rápido.
10. Como desenvolvedor, quero que `carregar_fornecedor(fornecedor_id)` continue no port mesmo sem caller atual, para não pagar custo de reintroduzi-lo quando M3 (`purchasing`) precisar de CNPJ pra emitir pedido.
11. Como desenvolvedor, quero que o `Ficha` (DTO de domínio retornado pelo `ficha_sku`) viva em `src/ficha_sku/schemas.py`, para respeitar o grafo de dependência da ADR-0001 (`api` → domínio, nunca o contrário).
12. Como desenvolvedor, quero o termo "ficha" registrado no `CONTEXT.md`, para que o vocabulário do domínio incorpore o novo conceito.
13. Como desenvolvedor, quero que `catalog.buscar_sku_por_codigo` deixe de existir (ou vire trivial delegação pra `erp.carregar_sku`), para eliminar a query "SELECT * FROM skus" em memória a cada request.
14. Como desenvolvedor, quero que o smoke test `tests/smoke/test_endpoints.py` continue passando sem mudança, para provar que o contrato HTTP permaneceu idêntico.

### Usuário-final (comprador chefe)

15. Como comprador chefe, quero que as URLs, os JSONs de resposta e os códigos de erro continuem exatamente iguais, para não perceber que houve refactor por baixo.

## Implementation Decisions

### Escopo do port `ERPAdapter`

Sete métodos, todos renomeados. Assinaturas:

- `carregar_sku(sku_code: str) -> SKU | None`
- `listar_skus() -> list[SKU]`
- `carregar_fornecedor(fornecedor_id: UUID) -> Fornecedor | None` (mantido apesar de sem caller atual, preparando M3)
- `fornecedores_de(sku_code: str) -> list[FornecedorParaSKU]` (SQL faz `WHERE ativo = true` e `ORDER BY preco_unitario_atual`)
- `estoque_de(sku_code: str) -> Estoque | None`
- `vendas_de(sku_code: str, desde: datetime) -> list[Venda]`
- `movimentacoes_de(sku_code: str, desde: datetime) -> list[Movimentacao]`

Assimetria intencional: SKU vai por `sku_code` (código de domínio), Fornecedor vai por UUID porque o schema `erp.fornecedores` não tem código legível.

### DTOs de domínio (donos e localização)

Cada conceito tem exatamente **um** DTO no seu módulo dono, e o adapter retorna esse DTO diretamente:

- `SKU` - vive em `src/catalog/schemas.py` (já existe; pode absorver campos hoje só em `SKURaw`)
- `Fornecedor` - novo, em `src/catalog/schemas.py`
- `FornecedorParaSKU` - vive em `src/catalog/schemas.py` (já existe)
- `Estoque` - vive em `src/inventory/schemas.py` (já existe)
- `Movimentacao` - novo, em `src/inventory/schemas.py`
- `Venda` - novo, em `src/sales/schemas.py`

Todos os `*Raw` em `src/erp_adapter/schemas.py` são **deletados**. O arquivo `schemas.py` do adapter pode desaparecer se ninguém mais depender dele.

### Camadas de DTO (a escada colapsa de 3 para 2)

- **Camada de domínio**: os DTOs listados acima. Consumidos pelos módulos, por outros DTOs de domínio (`Ficha` contém `SKU`, `Estoque`, etc), e devolvidos pelo adapter.
- **Camada HTTP**: `src/api/schemas.py` continua existindo, com `AnaliseSKUResponse`, `FornecedorResponse`, etc. Handler HTTP faz a projeção do DTO de domínio pra DTO de HTTP. Isso preserva liberdade de mudar o JSON público sem mexer em código de domínio.

### Filtros e ordenação no adapter

Regra: **operação que não depende de outro módulo** vai pro SQL. **Operação que depende** fica no módulo dono.

- `fornecedores_de`: filtro `ativo=true` e ordenação por preço vão pro `WHERE`/`ORDER BY`.
- `listar_skus`: pode aceitar opcionalmente `categoria: str | None` como filtro (não obrigatório no refactor - adicionar se conveniente).
- `abaixo_do_piso` **não muda de lugar**: continua em `inventory.abaixo_do_piso` porque depende de giro (que é `sales`) - respeita ADR.

### Módulo novo `ficha_sku`

Estrutura:

```
src/ficha_sku/
├── __init__.py
├── schemas.py         (contém Ficha)
├── service.py         (contém FichaSKU)
├── dependencies.py    (FastAPI Depends)
└── tests/
    ├── __init__.py
    └── test_ficha_sku.py
```

Interface do serviço:

```python
class FichaSKU:
    def __init__(self, catalog: Catalog, inventory: Inventory, sales: Sales) -> None: ...
    def completa(self, sku_code: str) -> Ficha | None
```

`Ficha` é um DTO Pydantic frozen composto por: `sku: SKU`, `estoque: Estoque`, `giro: Giro`, `cobertura: Cobertura`, `fornecedores: list[FornecedorParaSKU]`. Escopo idêntico ao que `/analise` devolve hoje - sem `vendas` nem `sazonalidade` (esses seguem nos endpoints separados).

Retorna `None` se o `sku_code` não existir. Handler HTTP traduz `None` em 404 (idêntico ao comportamento atual).

### Handler `/analise` após refactor

Passa a receber `FichaSKU` via `Depends`, chamar `ficha_sku.completa(sku_code)`, tratar `None` como 404, projetar o `Ficha` em `AnaliseSKUResponse` e retornar. Sem `Depends(get_catalog)`, `Depends(get_inventory)`, `Depends(get_sales)` no handler.

### `InMemoryERPAdapter`

Continua existindo com a mesma responsabilidade de hoje. Replicado 1:1:

- Métodos renomeados igual ao Postgres.
- Recebe listas de DTOs de domínio (`SKU`, `Fornecedor`, `Estoque`, ...) na construção - não mais `*Raw`.
- Aplica os mesmos filtros e ordenações que o Postgres (em Python, sobre as listas).

Divergência entre in-memory e Postgres continua sendo pega por `tests/test_seed_smoke.py` e `tests/smoke/test_endpoints.py`.

### Atualização do vocabulário

Adicionar termo ao `CONTEXT.md`, seção Métricas ou Sistemas:

> **Ficha (do SKU)**: composição de leitura que devolve o estado atual de um SKU pronto pra decisão de compra - dados do catálogo, estoque atual, giro, cobertura e fornecedores disponíveis. Materializada no módulo `ficha_sku` e servida pelo endpoint `/skus/{sku_code}/analise`.
> _Avoid_: análise (ambíguo), dashboard, resumo.

### Migração de `tests/fakes.py`

Os builders (`make_sku`, `make_fornecedor`, `make_fornecedor_sku`, `make_estoque`, `make_venda`, `make_movimentacao`) passam a devolver DTOs de domínio, não `*Raw`. Renomeios de campo (se houver) migram junto. Manter helper `uid()` que já existe.

## Testing Decisions

### Filosofia

Refactor "zero regressão": comportamento externo (HTTP) idêntico. Testes existentes são o oráculo. Se um teste existente precisar mudar de asserção (não só de setup), é sinal de que o refactor introduziu mudança de comportamento e precisa ser justificado.

### Seams de teste (do mais alto pro mais baixo)

1. **Seam de topo: contrato HTTP** - `src/api/tests/test_skus.py` e `tests/smoke/test_endpoints.py` **não mudam nenhuma asserção**. Se passam, comportamento externo está preservado. Rede de segurança principal do refactor.

2. **Seam por módulo de domínio** - `src/catalog/tests/`, `src/inventory/tests/`, `src/sales/tests/` continuam existindo. Setup dos testes muda (usa DTOs de domínio no lugar de `*Raw`), mas asserções continuam válidas.

3. **Seam do adapter** - `src/erp_adapter/tests/test_postgres_adapter.py` continua exercitando `PostgresERPAdapter` contra banco real. Testa os métodos renomeados; asserções sobre filtro `ativo=false` e ordenação por preço devem passar tanto no adapter quanto no in-memory.

4. **Seam novo do `ficha_sku`** - `src/ficha_sku/tests/test_ficha_sku.py`. Testa via `InMemoryERPAdapter` injetado em `Catalog + Inventory + Sales` compostos. Casos:
   - SKU existente com estoque, giro > 0, fornecedores → `Ficha` populada.
   - SKU inexistente → `None`.
   - SKU sem vendas → `Ficha` com `cobertura.sem_giro=True`, `fornecedores=[]`.

### Prior art

Toda a convenção de teste do spec 01 vale: unitários via `InMemoryERPAdapter`, integração do adapter via Postgres real, HTTP via `TestClient` com `dependency_overrides`, smoke test contra Postgres real com seed. Padrão de fake em `tests/fakes.py` continua vivo.

### Cobertura mínima antes de considerar o refactor pronto

- `uv run pytest` passa (75+ testes, incluindo smoke).
- Zero import de qualquer `*Raw` em `src/` (grep prova).
- `src/api/tests/test_skus.py` e `tests/smoke/test_endpoints.py` passam **sem alteração de asserção**.
- Novo teste `src/ficha_sku/tests/test_ficha_sku.py` cobre feliz, 404 e sem-giro.
- Filtro `ativo=true` em `fornecedores_de` verificado por teste do adapter (Postgres) e do in-memory.

## Out of Scope

- **Novos endpoints ou novos campos**. Comportamento externo é idêntico.
- **Adicionar giro/cobertura ao `ERPAdapter`**. Ficam onde estão (`sales`, `inventory`). ADR-0001 preservada.
- **Contract tests compartilhados entre Postgres e InMemory** (foi discutido e rejeitado no grilling; revisitar se divergência aparecer mais de uma vez).
- **Extrair `GiroProvider` como Protocol entre `inventory` e `sales`** (candidato 4 da revisão; adiado até segundo consumidor de giro aparecer, provavelmente em M3).
- **`ficha_sku` incluir `vendas` e `sazonalidade`** (candidato 3 opção B; adiado até M4 mostrar exatamente o que a tool do agente precisa).
- **Migrar `abaixo_do_piso` pra SQL** (candidato 1 opção C; adiado até dor real de performance).
- **Cache / batching / lifespan de FastAPI**. Instância nova por request continua.
- **Adicionar `criado_em` (do fornecedor) a nenhum DTO**. Não há caller.

## Further Notes

- Este spec é 100% refactor. Zero feature nova, zero mudança de comportamento externo. Todo ticket deve fechar com `uv run pytest` verde e `git diff` do JSON de qualquer endpoint = vazio.
- Origem da decisão: revisão via `/improve-codebase-architecture` (relatório efêmero em `/var/folders/tx/.../architecture-review-20260917-083634.html`), com grilling em 7 rodadas sobre a forma do adapter e do `ficha_sku`. Decisões consolidadas neste spec.
- Ordem sugerida dos tickets (a ser detalhada em `/to-tickets`):
  1. Renomear métodos do port + criar DTOs de domínio faltantes (`Fornecedor`, `Movimentacao`, `Venda`).
  2. Migrar `PostgresERPAdapter` pra devolver DTOs de domínio + SQL com filtro/ordenação.
  3. Migrar `InMemoryERPAdapter` pra receber e devolver DTOs de domínio.
  4. Adaptar `catalog`, `inventory`, `sales` pra consumir a nova interface.
  5. Deletar `src/erp_adapter/schemas.py` (todos os `*Raw`) e adaptar `tests/fakes.py`.
  6. Criar módulo `ficha_sku` + testes.
  7. Adaptar handler `/analise` pra usar `ficha_sku` + atualizar `CONTEXT.md`.
- Cada ticket deve manter todos os testes verdes ao final; se ordem obrigar código em estado transitório inconsistente, ticket é grande demais e deve ser dividido.
