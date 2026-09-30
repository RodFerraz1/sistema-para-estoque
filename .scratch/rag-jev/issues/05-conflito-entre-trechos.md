# 05: Conflito entre trechos

**Status:** done
**Blocked by:** 04 (Busca com filtro do Jev end-to-end)
**Spec:** `.scratch/rag-jev/spec.md`

## What to build

Depois de classificar, a busca compara dois a dois os trechos `aceito` e `conflitante` de documentos diferentes e sinaliza os pares que afirmam coisas incompatíveis sobre o mesmo fato. É o que faz "lead time da Katrina" mostrar que o contrato fala em 45 dias e a revisão Q1/2025 em 62. A busca só sinaliza: não escolhe o lado vencedor nem compara datas.

Se o spike (02) tiver mostrado que o Jev não separa os pares de conflito, este ticket foi cancelado lá e não deve ser feito.

## Acceptance criteria

- [x] `DecisionModel.avaliar_conflitos(pares) -> list[AvaliacaoConflito]` no port, no `JevDecisionModel` (pergunta e criteria da spec, na redação do spike, um request por par, até 8 em paralelo) e no `InMemoryDecisionModel`.
- [x] `BuscaContexto` monta os pares só entre `aceito` e `conflitante`, só entre documentos diferentes, e só com os 6 primeiros por similaridade (no máximo 15 pares). Com menos de 2 trechos elegíveis, não chama o Jev.
- [x] `LIMIARES.conflito` com o valor do spike. Par acima dele vira `ConflitoEntreTrechos` (`trecho_a`, `trecho_b`, `probabilidade`) em `ResultadoBusca.conflitos`.
- [x] `/rag/busca` devolve `conflitos` com os ids dos dois trechos e a probabilidade.
- [x] Testes com `InMemoryDecisionModel`: mesmo documento não gera par; `descartado` não entra; limite de 6 trechos; par abaixo do limiar não aparece; falha do Jev no conflito vira 503 (sem resultado parcial). `JevDecisionModel` com cliente falso para o state do par.
- [x] `uv run pytest` verde.

## Comments

**2026-09-30 (agente):** o spike mostrou que o `Noul` de conflito separa os pares rotulados (EN: acurácia 1,00 com limiar 0,10; PT: 0,90), então o ticket não é cancelado. A margem é pequena: os pares com conflito real ficam entre 0,11 e 0,61. Segue bloqueado pelo 04.

**2026-09-30 (agente):** pronto. `LIMIARES.conflito` é 0,10, comparado com `>`, e o limite de 6 trechos é `MAX_TRECHOS_CONFLITO` em `busca.py`. O `InMemoryDecisionModel` recebe `conflitos` por par (procurado nas duas ordens), `conflito_padrao` e `falhar_conflitos`. `trecho_a` é sempre o mais parecido com a pergunta, e os conflitos saem na ordem dos pares, não pela probabilidade.

O teste `externo` usa o par `contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato` x `reunioes/2025-q1-revisao-fornecedores.md#katrina-textil`, que deu 0,62 no spike. O par do exemplo acima (`#clausulas-comerciais/3-prazos` x revisão Q1) deu só 0,12, perto demais do limiar para um teste estável.
