# 05: README, smoke e rodada dos casos pelo chat

**Status:** ready-for-agent
**Blocked by:** 04
**Spec:** `.scratch/chat/spec.md`

## What to build

Fecha o M5: smoke do `/chat` contra Postgres e o Jev real, README com o chat e os casos de `evals/casos.json` rodados pelo chat inteiro para ver o comportamento real (intenção, faixa, ação, SKUs).

## Acceptance criteria

- [ ] Smoke `externo` em `tests/smoke/`: `POST /chat` de "Qual a situação do SKU TBC-BEGE-70140-01?" devolve `situacao_sku` com esse SKU, e o registro aparece em `GET /chat/registros`.
- [ ] `scripts/rodar_casos_chat.py`: roda as 20 perguntas de `evals/casos.json` pelo `Copilot` com o Jev real e o redator configurado, e imprime por caso a intenção esperada e a escolhida, a confiança, a faixa, a ação e os SKUs. Resultado resumido num comentário deste ticket.
- [ ] README: aviso do topo atualizado (M0-M5), variáveis novas, seção do chat com um exemplo real de `POST /chat` e de `GET /chat/registros`, módulos novos na estrutura.
- [ ] Roadmap: M5 marcado como concluído, com a data.
- [ ] `uv run pytest -q` verde (com `JEV_KEY`).

## Comments
