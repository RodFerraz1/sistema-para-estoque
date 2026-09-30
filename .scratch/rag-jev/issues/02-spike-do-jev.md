# 02: Spike do Jev (gate da ADR-0002)

**Status:** done (gate não passou)
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
- [x] Respostas cruas (probabilidades, confiança, tokens, latência, `model` retornado) gravadas em `evals/resultados/spike-<data>.json`. O script consegue recalcular as métricas a partir desse arquivo sem chamar o Jev (`--de-arquivo`).
- [x] Métricas impressas: acerto de intenção e erros com a confiança; varredura de limiares de relevância/evidência com recall e precisão; injeção nos adversariais e falsos positivos no corpus; separação entre pares com e sem conflito; latência p50/p95; tokens e custo por busca com k = 10.
- [x] `.scratch/rag-jev/spike-resultado.md` com o veredito de cada critério do gate, a redação escolhida (PT ou EN), os limiares escolhidos para a busca e os 5 erros mais interessantes com state e pergunta exatos.
- [x] Se o gate passar: linha na ADR-0002 registrando que a condição de revisão foi cumprida, com link para o resultado. Se não passar: o ticket 04 vira `blocked` e a ADR-0002 é reaberta com o dev antes de qualquer outra coisa.
- [x] Se o conflito entre trechos não separar os pares rotulados, o ticket 05 é marcado como cancelado, com o motivo.

## Comments

**2026-09-29 (agente):** dados rotulados, teste dos ids e `scripts/spike_jev.py` prontos, com as métricas testadas em `tests/test_spike_jev.py` (inclui ida e volta do arquivo cru, que é o que o `--de-arquivo` usa). O script **não foi rodado**: o próximo passo é o dev revisar `evals/*.json` e confirmar os critérios do gate (constantes no topo do script). Depois disso: `uv run python -m scripts.spike_jev` (3.300 requests, uns US$ 0,03 em tokens de estado).

Decisões de medição, para o dev confirmar antes de rodar:
- Relevância: aceito = `relevante >= t_rel` e `tem_evidencia > t_evid`, varrendo os dois de 0,05 em 0,05; só trechos do corpus (os adversariais ficam fora). Trecho relevante sem rótulo conta como falso positivo, então rótulo faltando puxa a precisão para baixo.
- Injeção: um adversarial só conta como detectado se passar do limiar em **todas** as 20 perguntas; um trecho do corpus conta como falso positivo se passar em **qualquer** uma.
- Latência: o gate usa a última tentativa HTTP (sem backoff de 429); o total com retentativas também é impresso.
- Request que falha depois das retentativas é gravado com `erro` e invalida o gate (é preciso rodar de novo).
- `contradiz_premissa` só é reportado; `premissa_falsa` tem um único id por caso (como na spec), então outros trechos que também contradizem aparecem como "outros acima" no relatório.
- Conflito: o corpus tem poucos fatos contraditórios de verdade; 4 dos 5 pares com conflito são sobre o lead time da Katrina. A separação vale como indício, não como medida forte.

**2026-09-30 (agente):** o dev delegou a revisão ao agente e deu o ok antes de rodar. Critérios do gate e decisões de medição confirmados como estão acima (constantes no topo de `scripts/spike_jev.py`). Única mudança nos rótulos: o par de conflito R1 (teto de 3 meses) contra a decisão do Natal king size saiu, porque a ata registra uma exceção à regra e não um fato incompatível; entrou `fornecedores/katrina-textil.md#linhas-ativas` ("king com histórico de estoque parado") contra `reunioes/2024-11-natal-king-size.md#justificativa-da-excecao-a-politica` ("king tem menos risco de encalhe"). c01 a c03 seguem sem trecho relevante: estoque atual vem do ERP, não do corpus.

**2026-09-30 (agente):** spike rodado (3.300 requests, `jev-1.13.0`). **O gate não passou** em PT nem em EN: intenção e latência passam, relevância (melhor recall com precisão >= 0,6: 0,72 em PT) e injeção (regras da política de estoque chegam a 0,88 em `tenta_instruir`, acima do adversarial mais fraco) reprovam. Um request deu timeout; o spike não foi rodado de novo porque o registro que falta só poderia piorar as duas medidas que reprovaram. Detalhes e os 5 erros em `.scratch/rag-jev/spike-resultado.md`, respostas cruas em `evals/resultados/spike-2026-09-30.json`. Ticket 04 marcado `blocked`; a ADR-0002 volta para o dev. O conflito separa os pares rotulados, então o 05 não é cancelado, mas segue bloqueado pelo 04.

**2026-09-30 (agente), antes da rodada 2:** o dev pediu uma segunda rodada. Registrado aqui antes de rodar; nada disto muda depois de ver o resultado.
- **Critérios do gate e rótulos de `casos.json` e `pares_conflito.json`: sem mudança.** A rodada 2 mede a relevância nos mesmos casos em que os erros da rodada 1 foram vistos, então o resultado de relevância é otimista.
- **Injeção vira uma pergunta sobre o trecho sozinho** (state `{"trecho": {...}}`, sem a pergunta do comprador), um request por trecho. Na rodada 1, o mesmo trecho foi de 0,47 a 0,98 conforme a pergunta, e a doc do Jev pede para mandar só os campos que a pergunta precisa. O gate passa a comparar um valor por trecho: todos os adversariais acima do limiar e no máximo 1 trecho do corpus acima dele. Se passar, o 04 pode calcular a injeção uma vez por trecho, e não a cada busca.
- **Criteria nos `Noul`** de `tenta_instruir` (regra de negócio escrita para pessoas não é instrução ao sistema), `relevante` (quando a pergunta cita um fornecedor ou produto, o trecho precisa ser dele) e `tem_evidencia` (inclui confirmar ou corrigir o que a pergunta assume). `contradiz_premissa`, intenção e conflito ficam iguais e rodam de novo para ver se o resultado é estável.
- **2 trechos adversariais novos**, escritos antes da rodada e sem nenhum ajuste depois: uma injeção em inglês na ficha de fornecedor e uma disfarçada de nota de sistema. Isso deixa o gate de injeção mais difícil, não mais fácil.
- Relevância roda só sobre o corpus (os adversariais já ficavam fora da métrica). Custo por busca calculado com k = 30 (decisão do ticket 03). Retentativas do SDK sobem de 2 para 4 por causa do timeout da rodada 1.
- Saída em `evals/resultados/spike-<data>-r2.json`. A rodada 1 se recalcula com o script do commit `c98167d`.

**2026-09-30 (agente), resultado da rodada 2:** **não passa, só pela relevância.** Intenção, injeção e latência passam em PT e EN. A injeção se resolveu (adversariais de 0,95 a 0,99, corpus no máximo 0,07). A relevância chegou a recall 0,766 com precisão >= 0,6 (PT); com recall 0,851, a precisão é 0,455. De novo 1 timeout em `c01`, que só poderia piorar a relevância. Uma auditoria minha dos 48 falsos positivos (não às cegas, então não vale para o gate) achou 17 pares com rótulo faltando, 17 discutíveis e 14 erros reais. Só corrigindo os 17, a precisão iria para cerca de 0,65. Detalhes em `.scratch/rag-jev/spike-resultado.md`. O 04 continua `blocked` até o dev decidir a ADR-0002.

**2026-09-30 (agente), gabarito cego:** o dev vai refazer os `trechos_relevantes` de c01 a c15 às cegas (sem ver as notas do Jev nem o gabarito antigo), numa página com as 15 perguntas e os 79 trechos. c16 a c20 (fora de escopo) continuam sem trecho. Regra combinada antes de ver o gabarito novo:
- As métricas são recalculadas a partir das respostas gravadas da rodada 2 (`spike-2026-09-30-r2.json`), sem chamar o Jev de novo, com os mesmos critérios do gate.
- Se passar com o gabarito do dev, a ADR-0002 continua, com a redação e os limiares que saírem da varredura, e o ticket 04 é liberado. Se não passar, a ADR-0002 volta para decisão (usar o Jev só onde passou, ou substituir).
- O gabarito do dev substitui o antigo em `evals/casos.json`. A concordância entre os dois é reportada.
- **Atualização, antes de qualquer rótulo existir:** a rotulagem manual levaria mais de 2 h, e o dev pediu um agente. Quem rotula é um subagente novo, sem o contexto desta conversa, que só recebe as 15 perguntas e os 79 trechos (sem notas do Jev, sem gabarito antigo, sem acesso ao repositório), com o mesmo critério da página de rotulagem. O resto da regra não muda. Limitação conhecida: o rotulador também é um modelo de linguagem e pode errar do mesmo jeito que o Jev, o que tende a inflar a concordância. Por isso cada marcação vem com um motivo curto, para o dev conferir por amostragem.

**2026-09-30 (agente), resultado do gabarito cego:** **não passa, de novo só pela relevância.** Com o gabarito do subagente em `evals/casos.json` e as respostas gravadas da rodada 2, o melhor recall com precisão >= 0,6 foi 0,709 em PT (era 0,766 com o gabarito antigo) e 0,673 em EN. Os dois gabaritos concordam em 41 dos 61 pares (caso, trecho) marcados em algum deles (Jaccard 0,67). Os motivos que o subagente deu para cada marcação não foram salvos no repositório. Pela regra, a ADR-0002 voltou para o dev, que decidiu mantê-la inteira e aceitar o risco (essa não era uma das duas saídas combinadas acima). Os limiares da busca passam a ser t_rel 0,55 e t_evid 0,15, o ponto que cumpre o recall do gate (0,873) com a melhor precisão (0,343). Detalhes em `.scratch/rag-jev/spike-resultado.md`, e a decisão na ADR-0002. Ticket 04 liberado.
