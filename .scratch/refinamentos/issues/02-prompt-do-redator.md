# 02: Prompt do redator, limpeza da redação e medida antes e depois

**Status:** done
**Blocked by:** 01
**Spec:** `.scratch/refinamentos/spec.md` (seção "Prompt do redator")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

As instruções do redator reescritas a partir do que as rodadas do M5 e do M6 mediram, uma limpeza em código que tira o hífen não separável e os colchetes lenticulares da redação, e o `reasoning_effort` na Groq. O efeito é medido com contagens automáticas na rodada dos casos, numa rodada de base com as instruções do M5 e em até três rodadas depois das mudanças.

Leia antes os comentários com as saídas reais: `.scratch/chat/issues/03-chat-end-to-end.md`, `.scratch/chat/issues/05-readme-e-smoke.md`, `.scratch/sinais-e-citacoes/issues/02-verificacao-de-citacoes.md` e `.scratch/sinais-e-citacoes/issues/03-chat-com-sinais-e-citacoes.md`.

Arquivos: `src/ai/redator.py` (`INSTRUCOES_REDATOR`, `limpar_redacao`), `src/ai/chat.py` (só `_redigir`), `src/ai/groq.py`, `src/db/config.py`, `.env.example`, `scripts/rodar_casos_chat.py`, `evals/casos_redator.json` (novo) e os testes de `redator`, `groq`, `chat` e do script.

## Acceptance criteria

- [x] `INSTRUCOES_REDATOR` com as 11 regras da spec (a redação pode mudar depois da observação; o sentido de cada regra fica).
- [x] `limpar_redacao(texto)` em `src/ai/redator.py` (U+2010 e U+2011 viram `-`, U+00A0 e U+202F viram espaço, `【】` viram `[]`), aplicada pelo `Copilot._redigir` à redação de todo redator com `usa_llm`, antes da verificação de citações. A do `RedatorSemLLM` não muda.
- [x] `GROQ_REASONING_EFFORT` em `Settings` e `.env.example` (padrão `low`; vazio não envia), mandado como `reasoning_effort` pelo `GroqRedator`.
- [x] `scripts/rodar_casos_chat.py` com `--casos ARQ` e as três contagens da spec por caso e no total (colchetes sem id de trecho, sinais citados, quantidades no texto), em funções puras testadas.
- [x] `evals/casos_redator.json` com as quatro perguntas da spec (sugestão de `TBC-BEGE-70140-01`, `JDCP-BRAN-QUEEN-02` e `CB-OFF--QUEEN-09`, situação de `TBC-BEGE-70140-01`).
- [x] Rodada de base (instruções do M5, contagens novas) e rodadas depois das mudanças, com a Groq e `--pausa 30`, nos 20 casos e em `casos_redator.json`; com `ANTHROPIC_API_KEY`, a final também com o Claude. Num comentário deste ticket: as contagens antes e depois, os casos de conta, conversão, recomendação de fornecedor ou opinião que ainda aparecem (lidos com `--respostas`), os vereditos das citações e se alguma redação da Groq caiu por conteúdo vazio. Fica a versão das instruções com o melhor resultado medido.
- [x] Nenhum U+2011 nas respostas da rodada final (garantido pela limpeza).
- [x] Testes da spec: `limpar_redacao`, limpeza no `Copilot` (LLM sim, sem LLM não), `reasoning_effort` presente e ausente, contagens do script.
- [x] `uv run pytest -q -m "not externo and not externo_llm"` verde e `-m externo_llm` passando.

## Fora do escopo

- Mudar a estrutura do contexto (`contexto.py`), a extração ou a marcação de citações.
- Verificar as contas do redator ou reescrever a resposta.
- `retry-after` na Groq.
- Os limiares do Jev (tickets 03, 04 e 05) e o README (ticket 06).

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões, desvios e números:

- **Instruções** (`INSTRUCOES_REDATOR`): as 11 regras da spec, ajustadas em duas voltas depois de ler as respostas. Fica a v3, a de melhor resultado medido. Mudanças de redação sobre o texto da spec, sem tirar o sentido de nenhuma regra:
  - regra 3: "não calcule datas nem prazos" (a v1 escreveu "o pedido deve ser feito até o início de setembro" no c09), "não diga se um número está acima, abaixo ou dentro de outro (cobertura contra teto ou piso)", "nem tire conclusão própria deles" e o alerta da sugestão como comparação pronta;
  - regra 4: a resposta "começa" pela seção, quantidade zero como "não comprar agora" com o motivo e "só depois responda o resto" (na v1 o c06 deixou de fora o `JDCP-CHAM-KING-06`, de quantidade zero);
  - regra 6: também "faz sentido ou é recomendável, nem o que o comprador deveria fazer", e na ficha de SKU os fornecedores listados sem escolher nenhum nem aplicar o critério da política (na v1 o p04 ainda dizia "Fornecedor recomendado (menor preço)");
  - regra 8: "nunca ponha dois colchetes seguidos", "nem código de SKU, nem regra, nem nome de seção do contexto" (a v1 e a v2 escreveram `[fichas de sku]`, `[contexto da sugestão]`, `[conflitos entre trechos]`, `[R3]`) e "se o contexto não tem trecho, não cite nada". **O exemplo deixou de ser um id real**: na v2 o p04 (ficha, sem nenhum trecho no contexto) citou o próprio exemplo da regra, `[contratos/contrato-katrina-2025.md#clausulas-comerciais/3-prazos]`, que saiu `inventada`; o exemplo agora é `[pasta/documento.md#secao]` e o teste deixou de exigir o id da Katrina nas instruções.
- **Desvio: `limpar_redacao` também tira o U+200B** (espaço de largura zero). Na rodada de base, o p01 escreveu as duas citações como `[\u200bfornecedores/katrina-textil.md#lead-time\u200b]`, e a extração não as viu: o p01 saiu com "Citações: -". A tolerância da extração continua como estava; a spec foi atualizada.
- **Limpeza no `Copilot._redigir`**: aplicada ao texto do redator configurado quando `usa_llm`, antes da verificação; o texto do `RedatorSemLLM` (sem chave ou na queda) sai igual.
- **Groq**: `GroqRedator(..., reasoning_effort="")`, que só vai no corpo quando não vazio; `GROQ_REASONING_EFFORT` como `str` com padrão `low` no `Settings` (sem lista fechada de valores: a Groq aceita valores diferentes por modelo) e no `.env.example`. O teste real da Groq usa o valor do `Settings`.
- **Script**: `--casos ARQ`, `Contagens` por caso e total, com `colchetes_sem_id`, `sinais_citados` e `quantidades_no_texto` como funções puras (`tests/test_rodar_casos_chat.py`). Colchete com id em qualquer parte, inclusive as marcas da verificação, não conta; sinal citado é o que tem algum trecho de origem entre as citações extraídas da redação; quantidade escrita é o número com milhar por ponto, solto (não conta `390` para 39 nem `1,39`). **Fora do pedido**: `RedatorComQuedas` envolve o redator e imprime o motivo da queda por caso e o total de quedas, porque o `Copilot` troca a queda pelo `RedatorSemLLM` sem expor o motivo e o ticket pede saber se alguma caiu por conteúdo vazio.
- **`evals/casos_redator.json`**: p01 a p04 com as perguntas que o M6 já tinha feito pelo chat (estão em `copilot.registros_decisao`): "Quanto devo comprar do SKU TBC-BEGE-70140-01?", "Quanto compro do JDCP-BRAN-QUEEN-02?", "Vale comprar a colcha CB-OFF--QUEEN-09 agora?" e "Qual a situação do SKU TBC-BEGE-70140-01?". Teste em `test_evals.py` (formato, ids únicos, intenções, sem repetir `casos.json`).
- **Rodadas**: Groq `openai/gpt-oss-120b` (`REDATOR=groq`), Jev `jev-1.13.0`, `--respostas --pausa 30`, um processo por rodada com os dois arquivos em seguida (o código fica carregado no início, então dava para editar a próxima versão durante a rodada). A base rodou com o código do M5 em `src/` (instruções de 7 regras, sem limpeza, sem `reasoning_effort`) e o script novo. Cada rodada gravou 24 registros de decisão. Sem `ANTHROPIC_API_KEY`, o Claude não rodou.

| Rodada | Colchetes sem id (casos + redator) | Sinais citados | Quantidades no texto | Citações (casos; redator) | Quedas |
|---|---|---|---|---|---|
| Base (M5) | 15 (9 + 6) | 1/3 | 2/5 | confirmada 17, incerta 4, inventada 1; sem_suporte 2, confirmada 1, incerta 1 | 0 |
| v1 (texto da spec, limpeza, `low`) | 4 (2 + 2) | 3/3 | 4/5 | confirmada 13, sem_suporte 1; sem_suporte 3, confirmada 2, incerta 2 | 0 |
| v2 | 2 (2 + 0) | 3/3 | 5/5 | confirmada 14, incerta 2, contradita 1, sem_suporte 1; confirmada 3, incerta 3, sem_suporte 2, inventada 1 | 0 |
| **v3 (fica)** | **0** | **3/3** | **5/5** | confirmada 15, incerta 2; confirmada 2, incerta 2, sem_suporte 1 | 0 |

  - Caracteres na saída da base: 23 U+2011, 143 U+202F, 10 U+200B e 4 pares `【】`. Em v1, v2 e v3: nenhum dos quatro (o U+200B só entrou na limpeza a partir da v2, mas a v1 não o escreveu). Nenhum U+2011 na rodada final.
  - Nenhuma redação caiu (nem por conteúdo vazio nem por 429) em nenhuma das quatro rodadas: 62 redações, todas pela Groq. Redações de 1,3 a 7,8 s na v3 (base de 1,4 a 25,1 s, o c09).
  - Intenção 19/20 e 4/4 em todas (o c11 de sempre, `situacao_sku` de 0,39 a 0,44).
- **O que a leitura da v3 ainda mostra**:
  - c06: o motivo do `JDCP-BRAN-KING-03` vira "atende à cobertura de 2,3 meses na chegada e ao teto de 3,0 meses" (comparação), fecha com uma conclusão própria ("não há indicação de que este ano a compra será limitada a 3 meses") e chama de "sinais do corpus" trechos de lead time, sem sinal na sugestão; uma frase com dois colchetes colados.
  - c09: "o pedido deve ser feito com antecedência suficiente para cobrir esse intervalo real" (recomendação branda, sem data calculada; a base dizia "faça o pedido já em julho").
  - c15: "o que pode ser interpretado como um risco de dependência", interpretação do redator.
  - p04: "entre o piso de alerta (0,7 meses) e o teto da política (3,0 meses)" é a frase pronta do contexto com os números; a recomendação de fornecedor e a comparação "margem para otimização" da base sumiram. p03 não opina mais (a base fechava com "Recomendação: só avançar se...").
  - Conversão de unidade: nenhuma nas rodadas depois das mudanças.
- **Vereditos**: as citações dos sinais de encalhe (p02, p03) saem `incerta` ou `sem_suporte` em todas as versões. A frase é a mensagem do sinal ("encalhe de Colcha Bouti ou da categoria dele numa compra anterior") e o trecho fala do jogo Veraneio: o Jev não confirma a generalização para a categoria. É da mensagem do sinal, não do prompt. Os sinais do c06 vieram vazios nos dois king nas quatro rodadas (no M6 o `JDCP-BRAN-KING-03` teve encalhe a 0,98), assunto dos limiares dos sinais (ticket 04).
- **Testes**: `uv run pytest -q -m "not externo and not externo_llm"` com 793 passando; `-m "not externo"` com 794 passando e 1 pulado (eram 766 e 1); `-m externo_llm` com 2 passando (Groq unitário e smoke) e 1 pulado (Claude, sem chave).
- **`.env.example`**: o commit leva só a linha `GROQ_REASONING_EFFORT=low`; a mudança do dev no `FASTEMBED_CACHE_PATH` ficou fora do índice. O README (variável nova e limites conhecidos) fica para o ticket 06.
