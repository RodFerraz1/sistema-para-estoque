# 03: Sugestão de pedido end-to-end

**Status:** done
**Blocked by:** 01 (Política de compra versionada), 02 (Estoque em trânsito)
**Spec:** `.scratch/sugestao-compra/spec.md`

## What to build

O comprador chama `GET /skus/{sku_code}/sugestao-compra` e recebe uma sugestão de pedido calculada na hora. Nasce o módulo `src/purchasing/` com `Purchasing.sugerir_pedido(sku_code)`. Esta fatia usa sempre o fornecedor mais barato (a ordem que `fornecedores_de` já devolve), aplica o mecanismo completo de posição, estoque na chegada, ponto de reposição e MOQ, e respeita `lead_time_base`. Critério de fornecedor, teto e os alertas comerciais ficam no ticket 04. Sazonalidade e SKU novo ficam no 05.

## Acceptance criteria

- [ ] `src/purchasing/` com `schemas.py`, `service.py`, `dependencies.py`, `tests/`.
- [ ] `SugestaoPedido`, `MemoriaCalculo`, `Alerta` e `MotivoSemCompra` conforme a spec. Nesta fatia o enum de motivos tem `sem_giro`, `sem_fornecedor` e `acima_do_ponto_de_reposicao`.
- [ ] `Purchasing` recebe `FichaSKU`, `Inventory`, `Sales`, `PoliticaCompraRepositorio` e `now` opcional. Não importa nada de `erp_adapter`.
- [ ] Motivos checados na ordem da spec. `sem_giro` e `sem_fornecedor` saem sem `calculo`.
- [ ] Cálculo conforme a spec: posição com em trânsito, `estoque_na_chegada`, `precisa_comprar` pelo piso de reposição, `qtd_necessaria` com piso + ciclo, arredondamento pra cima, MOQ.
- [ ] `lead_time_base` `observado` (fallback para o contratado quando nulo), `contratado` e `maior`, com `lead_time_origem` na memória de cálculo.
- [ ] Alerta `ruptura_antes_da_chegada`.
- [ ] `valor_estimado_centavos` e `politica_versao` preenchidos.
- [ ] SKU inexistente devolve `None` no serviço e 404 no HTTP. `SKUSemEstoque` devolve 500, como no `/analise`.
- [ ] DTO HTTP em `src/api/schemas.py`, handler no router de SKUs.
- [ ] Testes: o exemplo da spec reproduzido número a número; cada motivo; em trânsito reduzindo a quantidade; cada `lead_time_base`; MOQ arredondando; mudar a política muda a sugestão e a `politica_versao`; HTTP feliz, 404, e quantidade 0 com motivo.
- [ ] `uv run pytest` verde.
