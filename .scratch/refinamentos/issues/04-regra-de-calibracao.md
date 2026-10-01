# 04: Regra de calibração, limiares dos sinais e da citação

**Status:** ready-for-agent
**Blocked by:** nenhum
**Spec:** `.scratch/refinamentos/spec.md` (seção "Regra de calibração")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Uma regra de calibração única para os limiares do M8, em função pura, que não escolhe o extremo de um intervalo empatado, não move limiar sem amostra e registra a folga. Ela substitui as regras do M6 nos scripts dos sinais e da citação, e os limiares saem recalculados das respostas já gravadas no M6, sem chamar o Jev.

Leia antes os comentários com os números e os riscos: `.scratch/sinais-e-citacoes/issues/01-sinais-do-corpus.md` e `.scratch/sinais-e-citacoes/issues/02-verificacao-de-citacoes.md`.

Arquivos: `scripts/calibracao.py` (novo), `scripts/avaliar_sinais.py`, `scripts/avaliar_citacoes.py`, `src/ai/sinais.py` (`LIMIARES_SINAIS` e o comentário), `src/ai/citacoes.py` (`LIMIAR_CITACAO` e o comentário), `tests/test_calibracao.py` (novo), `tests/test_avaliar_sinais.py`, `tests/test_avaliar_citacoes.py` e os testes do `ai` que dependam dos valores antigos.

## Acceptance criteria

- [ ] `scripts/calibracao.py` com a regra da spec (amostra mínima, ponto médio, mais acertos com empate pelo ponto médio, erro crítico, arredondamento para o múltiplo de 0,05 entre os lados), devolvendo o limiar, a regra aplicada, a folga e o motivo.
- [ ] `avaliar_sinais.py` usa a regra por tipo, sem erro crítico, e imprime regra e folga de cada tipo. Docstring com a regra nova.
- [ ] `avaliar_citacoes.py` usa a regra com o erro crítico da spec (qualquer veredito errado entre as decididas) e imprime regra e folga. Docstring com a regra nova.
- [ ] `LIMIARES_SINAIS` e `LIMIAR_CITACAO` atualizados pelo resultado de `--de-arquivo` sobre `evals/resultados/sinais-2026-09-30.json` e `evals/resultados/citacoes-2026-09-30.json` (a conta de referência da spec dá atraso 0,80, venda por época 0,75, encalhe 0,55 e citação perto de 0,80; se a regra implementada der outro número, vale o da regra e o ticket explica a diferença). Os comentários das constantes apontam para este ticket.
- [ ] Comentário deste ticket com a saída dos dois scripts (limiar, regra, folga por tipo) e o efeito esperado no chat: quais trechos passam a virar sinal e quantas citações das redações reais do M6 mudariam de veredito (dá para recalcular sem chamar o Jev, com as confianças gravadas em `copilot.registros_decisao`).
- [ ] Testes da regra (cada ramo, arredondamento, sem múltiplo entre os lados) e dos scripts com a regra nova.
- [ ] `uv run pytest -q -m "not externo and not externo_llm"` verde.

## Fora do escopo

- Novos casos rotulados de sinais ou de citação, ou novas chamadas ao Jev.
- Mudar as perguntas dos sinais ou da citação, a extração de citações ou a afirmação por oração.
- Entendimento (ticket 03) e conflito (ticket 05), que usam a regra depois.
- Juntar os scripts de avaliação num módulo comum além de `calibracao.py`.

## Comments
