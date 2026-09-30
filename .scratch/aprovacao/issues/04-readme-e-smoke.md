# 04: README, smoke e fechamento do M7

**Status:** ready-for-agent
**Blocked by:** 03
**Spec:** `.scratch/aprovacao/spec.md`

## What to build

Fecha o M7: smoke do fluxo completo (gerar, aprovar, pedido no ERP, em trânsito descontado), README com a aprovação e a UI, roadmap atualizado.

## Acceptance criteria

- [ ] Smoke em `tests/smoke/`: gerar a fila contra o seed, aprovar a primeira pendente, conferir o pedido `aprovado` no ERP e a sugestão seguinte do mesmo SKU com o em trânsito descontado; rejeitar outra e conferir o status.
- [ ] README: aviso do topo (M0-M7), seção da fila de aprovação e da UI (como abrir), endpoints novos na tabela, estrutura de módulos.
- [ ] Roadmap: M7 concluído, com a data.
- [ ] `uv run pytest -q` verde (com `JEV_KEY`).

## Comments
