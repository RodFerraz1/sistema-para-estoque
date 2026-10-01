# 04: Escolha de fornecedor, teto e alertas comerciais

**Status:** done
**Blocked by:** 03 (Sugestão de pedido end-to-end)
**Spec:** `.scratch/sugestao-compra/spec.md`

## What to build

A sugestão deixa de usar sempre o mais barato e passa a escolher o fornecedor pelo `criterio_fornecedor` da política, pulando os que o MOQ empurraria acima do teto. Quando nenhum cabe, escolhe o primeiro pelo critério e avisa. Entram também os alertas de pedido mínimo e de lead time observado acima do contratado.

## Acceptance criteria

- [ ] Cada fornecedor candidato é calculado com o próprio lead time e o próprio MOQ.
- [ ] Ordenação por `criterio_fornecedor`: `menor_preco` (desempate por lead time) e `menor_lead_time` (desempate por preço). O lead time usado é o resolvido por `lead_time_base`.
- [ ] Escolhe o primeiro candidato que `cabe_no_teto`. Se nenhum couber, escolhe o primeiro da ordem e adiciona `viola_teto`, com a cobertura resultante na mensagem.
- [ ] Alerta `abaixo_pedido_minimo` quando `qtd * preco_unitario < pedido_minimo_reais * 100` (preço em centavos, pedido mínimo em reais).
- [ ] Alerta `lead_time_observado_acima_do_contratado` quando o escolhido tem observado maior que contratado, independente de `lead_time_base`.
- [ ] Testes: cada critério, com desempate; MOQ do mais barato estourando o teto e o seguinte sendo escolhido; nenhum cabendo gera `viola_teto`; cada alerta aparecendo e não aparecendo; o valor de pedido mínimo convertido corretamente.
- [ ] `uv run pytest` verde.
