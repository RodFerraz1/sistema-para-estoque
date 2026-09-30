# 03: Chat com sinais e citações verificadas, README e smoke

**Status:** ready-for-agent
**Blocked by:** 01, 02
**Spec:** `.scratch/sinais-e-citacoes/spec.md` (seção "Chat")

## What to build

O chat passa a usar os dois: a intenção `sugestao_compra` traz os sinais de cada sugestão no contexto e na resposta, e toda resposta redigida por LLM passa pela verificação de citações. O registro de decisão guarda sinais e verificações. Fecha o M6 com smoke, README e roadmap.

## Acceptance criteria

- [ ] `Copilot`: sinais por par (fornecedor, produto) nas sugestões; trechos de origem dos sinais no contexto (respeitando `MAX_TRECHOS_NO_CONTEXTO`, prioridade para os da pergunta); verificação só para redator LLM; queda do Jev nos sinais ou na verificação vira observação.
- [ ] `renderizar_contexto` mostra os sinais abaixo de cada sugestão, com os ids de origem.
- [ ] `RespostaCopilot` e o DTO HTTP de `POST /chat` com `sugestoes` com sinais e `citacoes`.
- [ ] Migration `0005` (`sinais` e `citacoes` jsonb em `copilot.registros_decisao`) e o registro gravando os dois.
- [ ] Smoke `externo`: sinais de um SKU da Katrina trazem `atraso_do_fornecedor`; `POST /chat` pedindo sugestão desse SKU traz os sinais.
- [ ] README (aviso do topo M0-M6, seção de sinais e citações com exemplo real) e roadmap (M6 concluído, com a data).
- [ ] `uv run pytest -q` verde (com `JEV_KEY`).

## Comments
