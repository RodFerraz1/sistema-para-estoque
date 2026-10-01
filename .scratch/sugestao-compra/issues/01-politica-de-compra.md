# 01: Política de compra versionada

**Status:** done
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/sugestao-compra/spec.md`
**ADR:** `docs/adr/0003-politica-de-compra-configuravel.md`

## What to build

Nasce o módulo `src/politica_compra/`. O comprador consegue ler a política ativa em `GET /politica-compra` e gravar uma versão nova em `PUT /politica-compra`. A política é um objeto tipado com os 10 parâmetros da spec, validado, gravado append-only em `copilot.politicas_compra`. A migration `0002` cria a tabela e insere a v1 com os valores da política v3. O endpoint `/skus/abaixo-do-piso` passa a usar `piso_alerta_dias` da política quando `dias` não é informado.

## Acceptance criteria

- [ ] Migration `0002` cria `copilot.politicas_compra` (uma coluna tipada por parâmetro, `meses_quentes` como `int[]`, `versao` PK crescente, `criada_em`) e insere a v1 com os valores literais da spec. `downgrade` remove a tabela.
- [ ] `ParametrosPolitica` (Pydantic frozen) com os 10 campos, enums `lead_time_base` (`observado`/`contratado`/`maior`), `criterio_fornecedor` (`menor_preco`/`menor_lead_time`) e `sazonalidade_modo` (`ignorar`/`alertar`), e todas as regras de validação da spec.
- [ ] `PoliticaCompra` com `versao`, `criada_em` e `parametros`.
- [ ] Port `PoliticaCompraRepositorio` com `ativa()` e `salvar_nova_versao(parametros)`. `PostgresPoliticaCompraRepositorio` e `InMemoryPoliticaCompraRepositorio` (que nasce com a v1 padrão).
- [ ] Nenhum `UPDATE` ou `DELETE` na tabela. A ativa é a de maior `versao`.
- [ ] `GET /politica-compra` devolve a ativa. `PUT /politica-compra` grava a versão nova e devolve 201. Parâmetro inválido devolve 422.
- [ ] `GET /skus/abaixo-do-piso` sem `dias` usa `piso_alerta_dias` da política. Com `dias`, o comportamento atual continua igual.
- [ ] Testes: validação (um caso inválido por regra), versionamento no InMemory, integração do repositório Postgres, HTTP de `GET`/`PUT`/422, `/abaixo-do-piso` sem `dias`.
- [ ] `uv run pytest` verde.
