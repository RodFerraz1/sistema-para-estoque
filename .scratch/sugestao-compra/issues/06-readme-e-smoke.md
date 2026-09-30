# 06: README e smoke test do M3

**Status:** done
**Blocked by:** 04 (Escolha de fornecedor, teto e alertas comerciais), 05 (Alerta sazonal e SKU novo)
**Spec:** `.scratch/sugestao-compra/spec.md`

## What to build

O smoke test passa a cobrir os endpoints do M3 contra Postgres com seed, e o README documenta a sugestão de pedido e a política de compra.

## Acceptance criteria

- [ ] `tests/smoke/test_endpoints.py` cobre `GET /politica-compra`, `PUT /politica-compra` (e o `GET` seguinte devolvendo a versão nova), `GET /skus/{sku_code}/sugestao-compra` (shape e status) e `/abaixo-do-piso` sem `dias`.
- [ ] Pelo menos um SKU do seed com pedido em trânsito aparece com `em_transito > 0` na memória de cálculo.
- [ ] README: endpoints novos na lista, exemplo de resposta de `/sugestao-compra`, módulos `politica_compra` e `purchasing` no diagrama, link pra ADR-0003 e pra `perguntas-comprador.md`. Remove a frase de que `purchasing` ainda não existe.
- [ ] `uv run pytest` verde, incluindo smoke.
