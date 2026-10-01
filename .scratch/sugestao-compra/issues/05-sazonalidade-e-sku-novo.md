# 05: Alerta sazonal e SKU novo

**Status:** done
**Blocked by:** 03 (Sugestão de pedido end-to-end)
**Spec:** `.scratch/sugestao-compra/spec.md`

## What to build

A sugestão avisa quando a compra vai chegar numa época forte (R2) e não sugere nada para SKUs novos sem histórico suficiente (R3), deixando a decisão pro comprador.

## Acceptance criteria

- [ ] Motivo `sku_novo` no enum, checado antes de `sem_giro`: a primeira venda tem menos de `dias_historico_minimo` dias em relação a `now`. SKU sem nenhuma venda continua `sem_giro`.
- [ ] `sales` expõe a data da primeira venda de um SKU (ou `None`), sem método novo no `ERPAdapter` a não ser que `vendas_de` não resolva.
- [ ] Alerta `periodo_sazonal` quando `sazonalidade_modo = alertar` e algum mês do calendário entre a chegada (`now + lead_time_dias`) e a chegada + `ciclo_compra_meses` está em `meses_quentes`. A mensagem cita os meses e a R2 (até `extra_sazonal_meses` a mais, com registro em ata).
- [ ] Com `sazonalidade_modo = ignorar`, o alerta nunca aparece.
- [ ] Testes: `sku_novo` na fronteira (um dia antes e um dia depois do mínimo); SKU sem vendas continua `sem_giro`; horizonte dentro, fora, e cruzando a virada do ano (ex: chegada em dezembro, ciclo de 2 meses); modo `ignorar`.
- [ ] `uv run pytest` verde.
