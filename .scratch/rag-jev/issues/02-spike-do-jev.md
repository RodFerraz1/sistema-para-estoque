# 02: Spike do Jev (gate da ADR-0002)

**Status:** ready-for-agent
**Blocked by:** 01 (Corpus em `corpus/` e leitura em trechos)
**Spec:** `.scratch/rag-jev/spec.md`
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Um conjunto de casos rotulados em `evals/` e o script `scripts/spike_jev.py`, que mede o Jev real em português contra o corpus: acerto de intenção, relevância de trecho, detecção de injeção, conflito entre trechos, latência e custo, com as instruções em português e em inglês. O resultado decide se a ADR-0002 continua. Precisa de `JEV_KEY`.

Antes de rodar o script, o dev revisa os casos rotulados e confirma os critérios do gate. Os critérios não mudam depois de ver o resultado.

## Acceptance criteria

- [x] `evals/casos.json` com 20 perguntas de comprador em português coloquial, cada uma com `intencao`, `trechos_relevantes` e `premissa_falsa`, conforme a spec (pelo menos 4 por intenção e pelo menos 2 com premissa falsa).
- [x] `evals/trechos_adversariais.json` com 2 trechos no formato de `Trecho`, cada um com um parágrafo final que tenta instruir o modelo.
- [x] `evals/pares_conflito.json` com 5 pares que se contradizem e 5 do mesmo assunto que não se contradizem.
- [x] Teste do pytest que confere que todo id citado em `evals/*.json` existe em `ler_corpus(corpus/)` (exceto os adversariais).
- [x] `scripts/spike_jev.py` roda intenção (`Choice`), relevância (os quatro `Noul` da spec, para cada pergunta contra cada trecho do corpus e os adversariais) e conflito (`Noul` por par), cada um em PT e em EN, com no máximo 8 requests em paralelo.
- [ ] Respostas cruas (probabilidades, confiança, tokens, latência, `model` retornado) gravadas em `evals/resultados/spike-<data>.json`. O script consegue recalcular as métricas a partir desse arquivo sem chamar o Jev (`--de-arquivo`).
- [ ] Métricas impressas: acerto de intenção e erros com a confiança; varredura de limiares de relevância/evidência com recall e precisão; injeção nos adversariais e falsos positivos no corpus; separação entre pares com e sem conflito; latência p50/p95; tokens e custo por busca com k = 10.
- [ ] `.scratch/rag-jev/spike-resultado.md` com o veredito de cada critério do gate, a redação escolhida (PT ou EN), os limiares escolhidos para a busca e os 5 erros mais interessantes com state e pergunta exatos.
- [ ] Se o gate passar: linha na ADR-0002 registrando que a condição de revisão foi cumprida, com link para o resultado. Se não passar: o ticket 04 vira `blocked` e a ADR-0002 é reaberta com o dev antes de qualquer outra coisa.
- [ ] Se o conflito entre trechos não separar os pares rotulados, o ticket 05 é marcado como cancelado, com o motivo.

## Comments

**2026-09-29 (agente):** dados rotulados, teste dos ids e `scripts/spike_jev.py` prontos, com as métricas testadas em `tests/test_spike_jev.py` (inclui ida e volta do arquivo cru, que é o que o `--de-arquivo` usa). O script **não foi rodado**: o próximo passo é o dev revisar `evals/*.json` e confirmar os critérios do gate (constantes no topo do script). Depois disso: `uv run python -m scripts.spike_jev` (3.300 requests, uns US$ 0,03 em tokens de estado).

Decisões de medição, para o dev confirmar antes de rodar:
- Relevância: aceito = `relevante >= t_rel` e `tem_evidencia > t_evid`, varrendo os dois de 0,05 em 0,05; só trechos do corpus (os adversariais ficam fora). Trecho relevante sem rótulo conta como falso positivo, então rótulo faltando puxa a precisão para baixo.
- Injeção: um adversarial só conta como detectado se passar do limiar em **todas** as 20 perguntas; um trecho do corpus conta como falso positivo se passar em **qualquer** uma.
- Latência: o gate usa a última tentativa HTTP (sem backoff de 429); o total com retentativas também é impresso.
- Request que falha depois das retentativas é gravado com `erro` e invalida o gate (é preciso rodar de novo).
- `contradiz_premissa` só é reportado; `premissa_falsa` tem um único id por caso (como na spec), então outros trechos que também contradizem aparecem como "outros acima" no relatório.
- Conflito: o corpus tem poucos fatos contraditórios de verdade; 4 dos 5 pares com conflito são sobre o lead time da Katrina. A separação vale como indício, não como medida forte.
