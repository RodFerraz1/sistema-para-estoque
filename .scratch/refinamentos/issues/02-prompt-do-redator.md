# 02: Prompt do redator, limpeza da redação e medida antes e depois

**Status:** ready-for-agent
**Blocked by:** 01
**Spec:** `.scratch/refinamentos/spec.md` (seção "Prompt do redator")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

As instruções do redator reescritas a partir do que as rodadas do M5 e do M6 mediram, uma limpeza em código que tira o hífen não separável e os colchetes lenticulares da redação, e o `reasoning_effort` na Groq. O efeito é medido com contagens automáticas na rodada dos casos, numa rodada de base com as instruções do M5 e em até três rodadas depois das mudanças.

Leia antes os comentários com as saídas reais: `.scratch/chat/issues/03-chat-end-to-end.md`, `.scratch/chat/issues/05-readme-e-smoke.md`, `.scratch/sinais-e-citacoes/issues/02-verificacao-de-citacoes.md` e `.scratch/sinais-e-citacoes/issues/03-chat-com-sinais-e-citacoes.md`.

Arquivos: `src/ai/redator.py` (`INSTRUCOES_REDATOR`, `limpar_redacao`), `src/ai/chat.py` (só `_redigir`), `src/ai/groq.py`, `src/db/config.py`, `.env.example`, `scripts/rodar_casos_chat.py`, `evals/casos_redator.json` (novo) e os testes de `redator`, `groq`, `chat` e do script.

## Acceptance criteria

- [ ] `INSTRUCOES_REDATOR` com as 11 regras da spec (a redação pode mudar depois da observação; o sentido de cada regra fica).
- [ ] `limpar_redacao(texto)` em `src/ai/redator.py` (U+2010 e U+2011 viram `-`, U+00A0 e U+202F viram espaço, `【】` viram `[]`), aplicada pelo `Copilot._redigir` à redação de todo redator com `usa_llm`, antes da verificação de citações. A do `RedatorSemLLM` não muda.
- [ ] `GROQ_REASONING_EFFORT` em `Settings` e `.env.example` (padrão `low`; vazio não envia), mandado como `reasoning_effort` pelo `GroqRedator`.
- [ ] `scripts/rodar_casos_chat.py` com `--casos ARQ` e as três contagens da spec por caso e no total (colchetes sem id de trecho, sinais citados, quantidades no texto), em funções puras testadas.
- [ ] `evals/casos_redator.json` com as quatro perguntas da spec (sugestão de `TBC-BEGE-70140-01`, `JDCP-BRAN-QUEEN-02` e `CB-OFF--QUEEN-09`, situação de `TBC-BEGE-70140-01`).
- [ ] Rodada de base (instruções do M5, contagens novas) e rodadas depois das mudanças, com a Groq e `--pausa 30`, nos 20 casos e em `casos_redator.json`; com `ANTHROPIC_API_KEY`, a final também com o Claude. Num comentário deste ticket: as contagens antes e depois, os casos de conta, conversão, recomendação de fornecedor ou opinião que ainda aparecem (lidos com `--respostas`), os vereditos das citações e se alguma redação da Groq caiu por conteúdo vazio. Fica a versão das instruções com o melhor resultado medido.
- [ ] Nenhum U+2011 nas respostas da rodada final (garantido pela limpeza).
- [ ] Testes da spec: `limpar_redacao`, limpeza no `Copilot` (LLM sim, sem LLM não), `reasoning_effort` presente e ausente, contagens do script.
- [ ] `uv run pytest -q -m "not externo and not externo_llm"` verde e `-m externo_llm` passando.

## Fora do escopo

- Mudar a estrutura do contexto (`contexto.py`), a extração ou a marcação de citações.
- Verificar as contas do redator ou reescrever a resposta.
- `retry-after` na Groq.
- Os limiares do Jev (tickets 03, 04 e 05) e o README (ticket 06).

## Comments
