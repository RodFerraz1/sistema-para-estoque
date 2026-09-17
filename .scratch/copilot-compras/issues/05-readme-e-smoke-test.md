# 05: README e smoke test end-to-end

**Status:** ready-for-agent
**Blocked by:** 04 (Endpoints de leitura complementares)
**Spec:** `.scratch/copilot-compras/spec.md`

## What to build

Um desenvolvedor que abre o repositório pela primeira vez consegue, a partir do `README.md`, entender o que é o projeto, como subir localmente, quais endpoints existem e como o código está organizado. Um teste smoke end-to-end roda contra Postgres real com seed populado e valida que todos os endpoints públicos respondem com o shape esperado - servindo de "regression net" pros próximos specs.

## Acceptance criteria

- [ ] `README.md` na raiz com seções: descrição curta do projeto (1 parágrafo apontando pra `CONTEXT.md`), pré-requisitos (Docker, `uv`, Python), comando pra subir localmente, comando pra rodar seed, comando pra rodar testes, lista de endpoints disponíveis com exemplo de resposta pra `/skus/{sku_code}/analise`, diagrama ASCII simples da estrutura de módulos apontando pro `docs/adr/0001-*.md`.
- [ ] README menciona explicitamente que este é um sistema em construção, que o corpus RAG e módulos `purchasing`/`ai` ainda não existem, e aponta pro `roadmap.md`.
- [ ] Teste smoke end-to-end em `tests/smoke/` que: sobe Postgres via fixture, roda migrations, roda seed, chama cada endpoint (`/health`, `/skus/{sku_code}/analise`, `/skus/abaixo-do-piso`, `/skus/{sku_code}/vendas`, `/skus/{sku_code}/sazonalidade`, `/skus/{sku_code}/fornecedores`), valida status code e shape de resposta (via Pydantic ou assertions estruturais).
- [ ] Teste smoke roda com `uv run pytest tests/smoke/` e passa em CI-like ambiente local.
- [ ] Instrução no README pra rodar apenas os testes smoke separadamente dos unitários.
