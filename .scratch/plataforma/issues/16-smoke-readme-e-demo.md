# 16: Smoke tests, README e roteiro de demo da plataforma

**What to build:** quem avaliar o projeto vê a plataforma inteira contando a história da reunião: o tapete marrom para de vender, o repositor é notificado, não acha no depósito, o comprador vê o estoque divergente, decide comprar, e numa outra ponta cobra o fornecedor de uma entrega atrasada, enquanto a vendedora consulta a previsão, avisa o repositor de uma gôndola vazia, o repositor monta a gôndola de tapetes com mais marrom que branco, e acompanha os avisos dela.

**Blocked by:** 08, 14, 15

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seções "Testing Decisions" e "Documentação e domínio")

- [ ] Smoke tests contra o Postgres: login, ruptura com notificação, queda de venda com verificação e estoque divergente, aviso de gôndola vazia com verificação, mix de gôndola, e entrega atrasada com cobrança.
- [ ] README com as telas por papel, o comando do primeiro admin e screenshots novas.
- [ ] Roteiro de demo com a história acima, usando os cenários do seed.
- [ ] As perguntas abertas da seção "Pormenores e suposições" da spec entram em `.scratch/sugestao-compra/perguntas-comprador.md`.
- [ ] Suíte completa, smoke e pyright sem erro novo.
