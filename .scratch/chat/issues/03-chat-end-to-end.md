# 03: `POST /chat` end-to-end com roteamento por confiança

**Status:** ready-for-agent
**Blocked by:** 01, 02
**Spec:** `.scratch/chat/spec.md` (seções "Faixas de confiança e roteamento", "Resposta do Copilot" e "Endpoints")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O comprador pergunta em `POST /chat` e recebe texto. O `Copilot` pede o entendimento ao Jev, decide pela faixa de confiança da intenção, identifica os SKUs, monta os dados pela intenção (fichas, sugestões, busca no corpus), renderiza o contexto e chama o redator. Esclarecimento e fora de escopo são respostas feitas em código, sem redator. A queda do redator cai no `RedatorSemLLM`.

## Acceptance criteria

- [ ] `src/ai/chat.py`: `Copilot.responder(pergunta) -> RespostaCopilot`, `FAIXAS`, `MAX_TRECHOS_NO_CONTEXTO`, textos de confirmação, esclarecimento e fora de escopo como na spec.
- [ ] Montagem por intenção como na spec: fichas e política para `situacao_sku`; sugestões, política e busca para `sugestao_compra`; busca para `politica_ou_fornecedor`. Só trechos `aceito` e `conflitante` chegam ao contexto, até o máximo.
- [ ] Faixa média prefixa a confirmação à redação; faixa baixa pede esclarecimento com as duas intenções mais prováveis; SKU não identificado pede esclarecimento com os candidatos.
- [ ] `RedatorIndisponivel` cai no `RedatorSemLLM` com a observação; `DecisaoIndisponivel` vira 503.
- [ ] `POST /chat` (`src/api/chat.py`) com DTOs HTTP, reaproveitando os conversores de ficha, sugestão e trecho. Router registrado em `create_app()`. `registro_id` pode ficar nulo até o ticket 04.
- [ ] Testes da spec para o `Copilot` (adapters em memória) e HTTP (feliz, 422, 503).
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
