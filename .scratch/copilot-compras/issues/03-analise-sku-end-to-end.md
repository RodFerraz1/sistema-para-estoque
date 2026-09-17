# 03: Análise de SKU end-to-end

**Status:** ready-for-agent
**Blocked by:** 02 (Schema `erp` e seed reproduzível)
**Spec:** `.scratch/copilot-compras/spec.md`
**Interfaces:** `.scratch/copilot-compras/module-interfaces.md`
**Arquitetura:** `docs/adr/0001-monolito-modular-por-dominio.md`

## What to build

O comprador chefe consegue chamar `GET /skus/{sku_code}/analise` e receber, em uma única resposta JSON, o retrato completo de um SKU: nome, categoria, estoque atual (disponível e reservado), giro médio mensal dos últimos 6 meses, cobertura em meses, e lista de fornecedores disponíveis com condições. Este ticket cria a espinha dorsal de módulos que todos os endpoints futuros vão reutilizar - `erp_adapter`, `catalog`, `inventory`, `sales` - com fronteiras respeitando ADR-0001.

## Acceptance criteria

- [ ] `erp_adapter` implementado como Port (`Protocol`) + `PostgresERPAdapter` (SQLAlchemy) + `InMemoryERPAdapter` (para testes). Métodos necessários: `get_sku_raw`, `list_skus_raw`, `get_fornecedor_raw`, `list_fornecedores_para_sku`, `get_estoque_atual`, `list_movimentacoes`, `list_vendas`.
- [ ] Módulo `catalog` expõe `get_sku`, `buscar_sku_por_codigo`, `list_fornecedores_para_sku`, com DTOs Pydantic próprios.
- [ ] Módulo `inventory` expõe `estoque_atual`, `cobertura_meses` (usa `Sales` para o giro), com DTOs próprios.
- [ ] Módulo `sales` expõe `giro_medio_mensal` conforme regra do spec (soma últimos 6 meses fechados / 6; se histórico menor, usa o disponível sem extrapolar).
- [ ] `cobertura_meses` retorna representação semântica de "sem giro" quando giro é zero, não erro numérico.
- [ ] SKUs identificados publicamente pelo `sku_code` legível, não pelo UUID (endpoint aceita `sku_code` no path).
- [ ] `GET /skus/{sku_code}/analise` retorna JSON com nome, categoria, estoque (disponível + reservada), giro médio, cobertura em meses, lista de fornecedores com preço/MOQ/lead time contratado/lead time observado.
- [ ] SKU inexistente retorna 404 com mensagem clara.
- [ ] Injeção de dependência via FastAPI `Depends` permite trocar `PostgresERPAdapter` por `InMemoryERPAdapter` em testes.
- [ ] Módulos não acessam tabelas de outros módulos; comunicação apenas via interfaces públicas (regra do ADR-0001).
- [ ] Testes unitários dos módulos `catalog`, `inventory`, `sales` usam `InMemoryERPAdapter` e cobrem: caminho feliz + edge cases (SKU sem vendas, giro zero, SKU inexistente).
- [ ] Testes de integração de `PostgresERPAdapter` rodam contra Postgres real e cobrem cada método público.
- [ ] Teste HTTP do endpoint `/analise` verifica status code e shape do JSON.
