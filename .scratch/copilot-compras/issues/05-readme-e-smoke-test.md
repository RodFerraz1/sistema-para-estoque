# 05: README e smoke test end-to-end

**Status:** done
**Blocked by:** 04 (Endpoints de leitura complementares)
**Spec:** `.scratch/copilot-compras/spec.md`

## What to build

Um desenvolvedor que abre o repositório pela primeira vez consegue, a partir do `README.md`, entender o que é o projeto, como subir localmente, quais endpoints existem e como o código está organizado. Um teste smoke end-to-end roda contra Postgres real com seed populado e valida que todos os endpoints públicos respondem com o shape esperado - servindo de "regression net" pros próximos specs.

## Acceptance criteria

- [x] `README.md` na raiz com seções: descrição curta do projeto (1 parágrafo apontando pra `CONTEXT.md`), pré-requisitos (Docker, `uv`, Python), comando pra subir localmente, comando pra rodar seed, comando pra rodar testes, lista de endpoints disponíveis com exemplo de resposta pra `/skus/{sku_code}/analise`, diagrama ASCII simples da estrutura de módulos apontando pro `docs/adr/0001-*.md`.
- [x] README menciona explicitamente que este é um sistema em construção, que o corpus RAG e módulos `purchasing`/`ai` ainda não existem, e aponta pro `roadmap.md`.
- [x] Teste smoke end-to-end em `tests/smoke/` que: sobe Postgres via fixture, roda migrations, roda seed, chama cada endpoint (`/health`, `/skus/{sku_code}/analise`, `/skus/abaixo-do-piso`, `/skus/{sku_code}/vendas`, `/skus/{sku_code}/sazonalidade`, `/skus/{sku_code}/fornecedores`), valida status code e shape de resposta (via Pydantic ou assertions estruturais).
- [x] Teste smoke roda com `uv run pytest tests/smoke/` e passa em CI-like ambiente local.
- [x] Instrução no README pra rodar apenas os testes smoke separadamente dos unitários.

## Comments

- 2026-09-29: entregue em `920106a` e corrigido agora.
  - **Fixture do smoke:** a de `tests/smoke/conftest.py` passou a rodar `alembic upgrade head` antes do seed. Antes ela só verificava se o banco estava migrado. O `pytest.skip` no nível do conftest também foi trocado, porque quebrava `uv run pytest tests/smoke/` com traceback quando o banco estava indisponível. Agora o skip fica dentro da fixture.
  - **README:** o exemplo passou a usar um SKU real do seed (`CB-AZUL-CASAL-05`), porque `TBC-BEG-70140` não existe. Entraram também o módulo `ficha_sku` e o grafo de dependências corrigido. Há ainda notas sobre as unidades monetárias e sobre o smoke recriar os dados locais.
  - **Desvio do critério "sobe Postgres via fixture":** o Postgres vem do `docker compose`, que é o padrão do ticket 01. A fixture só verifica se ele está no ar e pula os testes se não estiver.
  - **Verificação:** o smoke passa contra um banco vazio (migra e popula), pula limpo com o banco inacessível e passa contra o banco principal. A suíte completa dá 102 passed.
