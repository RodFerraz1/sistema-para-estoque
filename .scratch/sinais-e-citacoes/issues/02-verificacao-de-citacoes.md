# 02: Verificação de citações

**Status:** ready-for-agent
**Blocked by:** 01
**Spec:** `.scratch/sinais-e-citacoes/spec.md` (seção "Verificação de citações")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O código extrai de um texto redigido cada citação `[id]` com a frase que a contém, marca como fonte inexistente o id que não estava no contexto e pergunta ao Jev se o trecho citado sustenta, contradiz ou não trata da frase. Toda citação não confirmada com confiança é marcada no texto. O limiar sai de uma avaliação contra o Jev real.

## Acceptance criteria

- [ ] `src/ai/citacoes.py`: `extrair_citacoes`, `marcar_citacoes`, `Citacao`, `VerificacaoCitacao`, `LIMIAR_CITACAO` e a função que decide o veredito, como na spec.
- [ ] `DecisionModel.verificar_citacoes` com a `Choice` da spec, no `JevDecisionModel` e no `InMemoryDecisionModel`; `AvaliacaoCitacao` nos schemas.
- [ ] `evals/citacoes.json` escrito antes de rodar; `scripts/avaliar_citacoes.py` (com `--de-arquivo`) rodado contra o Jev real; respostas cruas em `evals/resultados/`; resultado e limiar escolhido num comentário deste ticket. O teste que confere os ids de `evals/` cobre o arquivo novo.
- [ ] Testes da spec para `citacoes` (funções puras) e `verificar_citacoes` (cliente falso e um `externo`).
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
