# 01: Entendimento da pergunta e identificação dos SKUs

**Status:** ready-for-agent
**Blocked by:** nenhum
**Spec:** `.scratch/chat/spec.md` (seções "Entendimento da pergunta", "Identificação dos SKUs" e "Avaliação do entendimento contra o Jev real")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O Jev responde, num request, a intenção da pergunta e o produto do catálogo que ela cita. O código acha o código de SKU escrito na pergunta ou, sem código, usa o produto do Jev e estreita pelos SKUs com a cor e o tamanho citados. A escolha do produto é medida contra o Jev real antes de ser usada, e o limiar sai dessa medida.

## Acceptance criteria

- [ ] `Intencao`, `Escolha`, `Entendimento` e `ProdutoCatalogo` em `src/ai/schemas.py`, como na spec.
- [ ] `DecisionModel.entender_pergunta(pergunta, produtos) -> Entendimento`, implementado no `JevDecisionModel` (intenção com a redação PT exata do spike, produto com uma opção por produto mais `nenhum`, um request só) e no `InMemoryDecisionModel` (configurável por pergunta, com padrão e modo de falha).
- [ ] `Catalog.listar_skus()`.
- [ ] `src/ai/identificacao.py` com `produtos_do_catalogo`, `identificar_skus`, `Identificacao`, `LIMIAR_PRODUTO` e `MAX_SKUS_POR_RESPOSTA`, com as regras da spec.
- [ ] `produtos_aceitos` em cada caso de `evals/casos.json`, escrito antes de rodar o script. O teste que confere os ids de `evals/` passa a conferir também que todo produto citado existe no catálogo do seed (ou é `nenhum`).
- [ ] `scripts/avaliar_entendimento.py` (com `--de-arquivo`) rodado contra o Jev real (`JEV_KEY` está no `.env`), com as respostas cruas em `evals/resultados/entendimento-<data>.json`. Resultado (acerto da intenção, acerto do produto, varredura do limiar) registrado num comentário deste ticket, e `LIMIAR_PRODUTO` fixado pela regra da spec.
- [ ] Testes da spec para `identificacao` e `entender_pergunta` (cliente falso e um `externo`).
- [ ] `uv run pytest -q -m "not externo"` verde e os `externo` novos passando.

## Comments
