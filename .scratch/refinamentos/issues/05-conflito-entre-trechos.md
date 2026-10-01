# 05: Limiar de conflito entre trechos com pares reais

**Status:** ready-for-agent
**Blocked by:** 03, 04
**Spec:** `.scratch/refinamentos/spec.md` (seções "Conflito entre trechos" e "Regra de calibração")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O limiar de conflito (0,10) separou os 10 pares rotulados do spike com folga de 0,01, e nas buscas reais deixa passar pares com 12% de probabilidade, o que inunda a seção de conflitos do chat. Este ticket rotula pares reais que passaram, mede a pergunta do Jev com um script de avaliação e fixa o limiar pela regra do ticket 04. Se o limiar não separar com folga, os critérios da pergunta são reescritos uma vez a partir do `CONTEXT.md` e medidos de novo.

Bloqueado pelo 03 porque os dois mexem em `src/ai/jev.py` e `src/ai/tests/test_evals.py`, e pelo 04 por causa de `scripts/calibracao.py`. Leia antes `.scratch/rag-jev/spike-resultado.md` (seção do conflito) e o comentário do ticket 03 do M7 (`.scratch/aprovacao/issues/03-ui.md`). Para reescrever os critérios, invoque a skill `typesafe:typesafe-ai` e leia https://docs.typesafe.ai/primitives/noul.md.

Arquivos: `scripts/avaliar_conflitos.py` (novo), `evals/pares_conflito.json`, `src/ai/busca.py` (`LIMIARES.conflito` e o comentário de `Limiares`), `src/ai/jev.py` (só `PERGUNTAS_CONFLITO`, se reescrever), `src/ai/tests/test_evals.py`, `tests/test_avaliar_conflitos.py` (novo).

## Acceptance criteria

- [ ] Pares reais juntados rodando a busca com conflitos nas perguntas de `casos.json` que vão ao corpus; pelo menos 10 deles em `evals/pares_conflito.json`, rotulados às cegas pelo texto dos trechos (`conflitam`, `motivo`) antes de rodar a avaliação. `test_evals.py` exige pelo menos 5 pares de cada rótulo, entre documentos diferentes.
- [ ] `scripts/avaliar_conflitos.py` no padrão dos outros scripts de avaliação (respostas cruas em `evals/resultados/conflitos-<data>-<rotulo>.json`, `--de-arquivo`, varredura de 0,05 a 0,90) com a regra de calibração sem erro crítico, imprimindo limiar, regra e folga. Funções puras testadas.
- [ ] Se a regra der `mais_acertos` ou folga menor que 0,05: `PERGUNTAS_CONFLITO` com critérios estruturados pela definição do `CONTEXT.md` (contratado contra observado do mesmo fornecedor é conflito; opinião, recomendação e fatos diferentes não são), sem copiar pares rotulados, e nova medida. Fica a versão de mais acertos.
- [ ] `LIMIARES.conflito` com o limiar resultante e o comentário do `Limiares` apontando para este ticket.
- [ ] Comentário deste ticket com: quantos pares reais passavam do limiar antigo por pergunta, a saída das medidas, a decisão sobre a pergunta e quantos conflitos por pergunta passam com o limiar novo nas mesmas buscas.
- [ ] Os testes da busca que dependem do valor antigo atualizados; `uv run pytest -q -m "not externo and not externo_llm"` verde e os `externo` da busca passando.

## Fora do escopo

- Limitar a quantidade de conflitos mostrados no chat ou mudar como o contexto os renderiza.
- Os outros limiares da busca (relevância, evidência, injeção, premissa).
- README (ticket 06).

## Comments
