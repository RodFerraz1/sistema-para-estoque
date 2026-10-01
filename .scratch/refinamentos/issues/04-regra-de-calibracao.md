# 04: Regra de calibração, limiares dos sinais e da citação

**Status:** done
**Blocked by:** nenhum
**Spec:** `.scratch/refinamentos/spec.md` (seção "Regra de calibração")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Uma regra de calibração única para os limiares do M8, em função pura, que não escolhe o extremo de um intervalo empatado, não move limiar sem amostra e registra a folga. Ela substitui as regras do M6 nos scripts dos sinais e da citação, e os limiares saem recalculados das respostas já gravadas no M6, sem chamar o Jev.

Leia antes os comentários com os números e os riscos: `.scratch/sinais-e-citacoes/issues/01-sinais-do-corpus.md` e `.scratch/sinais-e-citacoes/issues/02-verificacao-de-citacoes.md`.

Arquivos: `scripts/calibracao.py` (novo), `scripts/avaliar_sinais.py`, `scripts/avaliar_citacoes.py`, `src/ai/sinais.py` (`LIMIARES_SINAIS` e o comentário), `src/ai/citacoes.py` (`LIMIAR_CITACAO` e o comentário), `tests/test_calibracao.py` (novo), `tests/test_avaliar_sinais.py`, `tests/test_avaliar_citacoes.py` e os testes do `ai` que dependam dos valores antigos.

## Acceptance criteria

- [x] `scripts/calibracao.py` com a regra da spec (amostra mínima, ponto médio, mais acertos com empate pelo ponto médio, erro crítico, arredondamento para o múltiplo de 0,05 entre os lados), devolvendo o limiar, a regra aplicada, a folga e o motivo.
- [x] `avaliar_sinais.py` usa a regra por tipo, sem erro crítico, e imprime regra e folga de cada tipo. Docstring com a regra nova.
- [x] `avaliar_citacoes.py` usa a regra com o erro crítico da spec (qualquer veredito errado entre as decididas) e imprime regra e folga. Docstring com a regra nova.
- [x] `LIMIARES_SINAIS` e `LIMIAR_CITACAO` atualizados pelo resultado de `--de-arquivo` sobre `evals/resultados/sinais-2026-09-30.json` e `evals/resultados/citacoes-2026-09-30.json` (a conta de referência da spec dá atraso 0,80, venda por época 0,75, encalhe 0,55 e citação perto de 0,80; se a regra implementada der outro número, vale o da regra e o ticket explica a diferença). Os comentários das constantes apontam para este ticket.
- [x] Comentário deste ticket com a saída dos dois scripts (limiar, regra, folga por tipo) e o efeito esperado no chat: quais trechos passam a virar sinal e quantas citações das redações reais do M6 mudariam de veredito (dá para recalcular sem chamar o Jev, com as confianças gravadas em `copilot.registros_decisao`).
- [x] Testes da regra (cada ramo, arredondamento, sem múltiplo entre os lados) e dos scripts com a regra nova.
- [x] `uv run pytest -q -m "not externo and not externo_llm"` verde.

## Fora do escopo

- Novos casos rotulados de sinais ou de citação, ou novas chamadas ao Jev.
- Mudar as perguntas dos sinais ou da citação, a extração de citações ou a afirmação por oração.
- Entendimento (ticket 03) e conflito (ticket 05), que usam a regra depois.
- Juntar os scripts de avaliação num módulo comum além de `calibracao.py`.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões, desvios e números:

- **Regra** em `scripts/calibracao.py`, como a spec, com duas funções puras: `calibrar(positivos, negativos, atual) -> Calibracao` e `calibrar_erro_critico(erros, acertos, atual) -> Calibracao`. `Calibracao` tem `limiar`, `regra` (`amostra_insuficiente`, `ponto_medio`, `mais_acertos`, `erro_critico`), `motivo`, `atual`, `lados` (os dois valores da amostra que cercam o limiar) e a `folga` derivada (distância do limiar a cada lado). `descrever(calibracao)` monta a linha do relatório e `formatar_limiar(valor)` imprime com duas casas, ou três quando precisa. São essas as assinaturas que os tickets 03 e 05 usam.
- **Desvio: sem o parâmetro `limiares`.** Na regra `mais_acertos`, as faixas saem dos próprios valores da amostra (de um valor ao seguinte, com 0 e 1 nas pontas), e não da varredura de 0,05 de cada script. É a varredura com passo infinitamente fino: o limiar nunca coincide com um valor da amostra, então tanto faz o limiar ser estrito (sinais) ou não (citação, faixas, produto), e a folga é medida até os dados, e não até o ponto da varredura. As varreduras continuam nos relatórios, só para leitura. Spec atualizada na linha da implementação.
- **Decisões da regra** que a spec não fixava: no empate entre faixas separadas de mais acertos, fica a mais larga e, entre as igualmente largas, a mais perto do limiar atual (o meio de um intervalo que junta duas faixas separadas pode cair numa faixa pior). No arredondamento, a mesma distância de dois múltiplos de 0,05 fica com o maior; quando o ponto médio com duas casas cairia num dos lados (lados 0,70 e 0,71), ganha a terceira casa (0,705). No erro crítico sem acerto acima do maior erro, o lado de cima é 1; com erro de confiança 1, nenhum limiar barra, e o atual fica com a regra `erro_critico` e o motivo.
- **Citação, erro crítico**: qualquer `escolha` diferente do rótulo entre as decididas, o que inclui também `sem_suporte` para trecho que sustenta (a spec cita só `confirmada` e `contradita` como exemplos). Nas respostas do M6 os três erros são os trechos de outro fornecedor lidos como `contradiz`.
- **Saída de `--de-arquivo`** (antes de mudar as constantes, por isso o "atual" é o valor antigo):
  - `atraso_do_fornecedor`: 0.80 (ponto_medio, folga 0.13 abaixo e 0.14 acima; separável entre 0.67 e 0.94; atual 0.90)
  - `demanda_sazonal`: 0.75 (mais_acertos, folga 0.06 abaixo e 0.07 acima; 21/22 acertos entre 0.69 e 0.82; atual 0.80)
  - `encalhe`: 0.55 (ponto_medio, folga 0.07 abaixo e 0.10 acima; separável entre 0.48 e 0.65; atual 0.60)
  - citação: 0.80 (erro_critico, folga 0.04 abaixo e 0.06 acima; 3 erros críticos; entre o maior erro e o menor acerto acima dele, 0.76 e 0.86; atual 0.50)
  - Iguais à conta de referência da spec. **Antes/depois**: `LIMIARES_SINAIS` de 0,90 / 0,80 / 0,60 para 0,80 / 0,75 / 0,55; `LIMIAR_CITACAO` de 0,50 para 0,80. Rodar de novo com as constantes novas dá os mesmos limiares (só o "atual" muda).
- **Efeito nos sinais**: nos 22 casos rotulados nenhum veredito muda (nenhuma probabilidade cai entre o limiar novo e o antigo de cada tipo); o acerto continua 22/22, 21/22 e 22/22. Fora da amostra, a justificativa do Natal king size (`reunioes/2024-11-natal-king-size.md#justificativa-da-excecao-a-politica`, atraso da Katrina com 0,86 para a toalha) passa a virar sinal de atraso. Todos os limiares desceram, então nenhum sinal que existia some. O registro de decisão não serve para dizer quais trechos novos passam: ele grava só os sinais que passaram do limiar antigo, com a maior probabilidade, e não as probabilidades de cada trecho avaliado. Recalcular isso pede chamar o Jev de novo, fora do escopo.
- **Efeito nas citações**, recalculado com as confianças gravadas em `copilot.registros_decisao` (só as redações da Groq, sem chamar o Jev; nenhuma citação repetida entre registros mudou a conta):
  - Redações do M6 (2026-09-30): 23 citações em 11 respostas, de 18 `confirmada`, 1 `sem_suporte` e 4 `incerta` para 13 `confirmada` e 10 `incerta`; mudam 6 (5 `confirmada` e 1 `sem_suporte` com confiança de 0,51 a 0,75). Entre elas, "Não há registro de encalhe do king size da Katrina no Natal 2024" (confirmada com 0,75, a negação de sinal que o ticket 02 combate) e "Sim, a antecipação faz sentido" (0,61, opinião do redator).
  - Contando também as rodadas do M8 (2026-10-01, tickets 01 e 02): 124 citações, mudam 20 (14 `confirmada`, 5 `sem_suporte` e a única `contradita`, de 0,62, que marcava "o trecho diz o contrário" numa frase de cobertura que o trecho da reunião do Natal nem trata). Nenhuma `contradita` sobra.
  - Consequência aceita pela spec: mais "não confirmada" no chat.
- **Duplicação dos scripts** (achado da revisão do M6): só o que é da regra foi para `calibracao.py` (a regra, a descrição e o formato do limiar). `main()`, `rodar()`, `avaliacoes()` e a latência continuam em cada script, porque juntá-los está fora do escopo da spec e do ticket. `escolher_limiar` e `LIMIAR_SEM_ZERO` saíram; no lugar, `calibrar_tipo` (sinais) e `calibrar_limiar` (citação) montam positivos e negativos e chamam a regra com o limiar atual do código.
- **Testes**: `tests/test_calibracao.py` (cada regra, empate entre faixas separadas, faixa até 1, arredondamento, empate no arredondamento, sem múltiplo entre os lados, terceira casa, erro crítico sem acerto acima e com confiança 1) e os testes dos dois scripts reescritos para a regra (casos novos para chegar a 3 positivos e 3 negativos, e a 3 erros críticos na citação). Nenhum teste do `ai` dependia dos valores antigos. `uv run pytest -q -m "not externo and not externo_llm"` com 810 passando; `-m "not externo"` com 811 passando e 1 pulado (eram 794).
