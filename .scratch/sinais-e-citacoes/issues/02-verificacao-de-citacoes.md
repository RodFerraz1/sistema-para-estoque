# 02: Verificação de citações

**Status:** done
**Blocked by:** 01
**Spec:** `.scratch/sinais-e-citacoes/spec.md` (seção "Verificação de citações")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O código extrai de um texto redigido cada citação `[id]` com a frase que a contém, marca como fonte inexistente o id que não estava no contexto e pergunta ao Jev se o trecho citado sustenta, contradiz ou não trata da frase. Toda citação não confirmada com confiança é marcada no texto. O limiar sai de uma avaliação contra o Jev real.

## Acceptance criteria

- [x] `src/ai/citacoes.py`: `extrair_citacoes`, `marcar_citacoes`, `Citacao`, `VerificacaoCitacao`, `LIMIAR_CITACAO` e a função que decide o veredito, como na spec.
- [x] `DecisionModel.verificar_citacoes` com a `Choice` da spec, no `JevDecisionModel` e no `InMemoryDecisionModel`; `AvaliacaoCitacao` nos schemas.
- [x] `evals/citacoes.json` escrito antes de rodar; `scripts/avaliar_citacoes.py` (com `--de-arquivo`) rodado contra o Jev real; respostas cruas em `evals/resultados/`; resultado e limiar escolhido num comentário deste ticket. O teste que confere os ids de `evals/` cobre o arquivo novo.
- [x] Testes da spec para `citacoes` (funções puras) e `verificar_citacoes` (cliente falso e um `externo`).
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Avaliação** (`evals/citacoes.json`, 28 pares escritos à mão antes de rodar, cada um com o `motivo` do rótulo): 10 `sustenta`, 9 `contradiz` e 9 `nao_trata`. Número trocado (c01 "a Katrina entrega em 30 dias", c02 antecedência de 30 dias, c05 teto de 5 meses, c09 reajuste acima de 8%), verdade sobre outro fornecedor (n01 a n03), a frase certa citando a faixa de aprovação errada (n04), mesma palavra com outro assunto (n06, categoria malha contra o fornecedor Malha Fina) e frases reais do redator no M5 (v04 a v06, e v09 e v10, uma frase com duas citações em que cada trecho só sustenta metade; rotulei `sustenta`, o comportamento desejado, para medir o alarme falso da frase inteira).
- **Resultado** (`evals/resultados/citacoes-2026-09-30.json`, `jev-1.13.0`, 28 requests, latência mediana 0,27 s e máxima 0,36 s; recalcula com `uv run python -m scripts.avaliar_citacoes --de-arquivo evals/resultados/citacoes-2026-09-30.json`):
  - Acerto da escolha: `sustenta` 10/10 (0,87 a 1,00, menos o v09 com 0,41), `contradiz` 9/9 (0,86 a 1,00; os números trocados deram 0,97 a 1,00), `nao_trata` 6/9. Os três erros são as verdades sobre outro fornecedor, que o Jev leu como `contradiz` (n01 0,76, n03 0,68, n02 0,60).
  - Nenhum par que não sustenta a afirmação foi escolhido como `sustenta`, em nenhuma confiança.
  - Varredura (incertas / erros entre as decididas / confirmadas erradas): 0,50: 2/3/0; 0,55 e 0,60: 3/3/0; 0,65: 4/2/0; 0,70 e 0,75: 5/1/0; 0,80 e 0,85: 6/0/0; 0,90: 8/0/0; 0,95: 9/0/0.
  - **`LIMIAR_CITACAO = 0,50`**, o menor limiar sem `confirmada` errada, pela regra da spec (a receita partia de 0,80).
- **Risco registrado**: em 0,50, citação de trecho de outro fornecedor sai `contradita` ("o trecho diz o contrário") em vez de `sem_suporte` ("não confirmada"). As duas marcam a citação, então o comprador não confia nela, mas a marca diz algo falso sobre o trecho. Em 0,80 esses três casos ficariam `incerta` (mesma marca de `sem_suporte`) e sobrariam 0 erros, ao custo de 4 incertas a mais. Não mudei o limiar depois de ver o resultado (mesma regra do spike e do ticket 01); é o primeiro candidato para o M8. A amostra é pequena e nenhum caso chegou perto de uma `confirmada` errada, então a regra não teve o que discriminar.
- **Com as redações reais do M5** (as 12 respostas distintas da Groq com trechos em `copilot.registros_decisao`, contra o Jev real, sem gravar nada): 33 citações de trecho, 26 `confirmada` e 7 `incerta` (confiança de 0,27 a 0,48), nenhuma `inventada` nem `contradita`. As incertas são quase todas frases com duas citações ou com uma conclusão do redator ("Portanto, embora a política..."): a afirmação é a frase inteira, como a spec pede, e o trecho só sustenta parte dela. Alarme falso aceito (o texto só é marcado); afirmação por oração fica para o M8. Os colchetes `【】`, o U+2011 e os `[SKU/...]` dessas respostas foram tratados como abaixo.
- **DTOs em `src/ai/schemas.py`**, e não em `citacoes.py` como o ticket diz: `Citacao`, `AvaliacaoCitacao`, `VerificacaoCitacao` e os `Literal` `Relacao` e `Veredito` (regra de ouro de `module-interfaces.md`; o ticket 03 põe `VerificacaoCitacao` na `RespostaCopilot`).
- **Funções de `src/ai/citacoes.py`**: `extrair_citacoes(texto)`, `marcar_citacoes(texto, verificacoes)`, `veredito(avaliacao, limiar=LIMIAR_CITACAO)` (a regra da spec para uma avaliação; o script usa o mesmo código com outros limiares), `decidir_vereditos(citacoes, ids_no_contexto, avaliacoes)` e `conferir_citacoes(texto, trechos, decisao)`. `decidir_vereditos` dá `incerta` com `confianca=None` para a citação do contexto sem avaliação, então com `avaliacoes=[]` ela já é a saída do Jev fora do ar (as inventadas continuam inventadas). `conferir_citacoes` extrai, pergunta ao Jev uma vez por par (afirmação, trecho) só para ids do contexto e decide; propaga `DecisaoIndisponivel` (tratar a queda como observação é do ticket 03). Confiança igual ao limiar decide ("abaixo do limiar" é `incerta`).
- **Formato do id**: só `<caminho>.md#<slug>` (com o sufixo `~N` das partes). `[SKU/TBC-BEGE-70140-01]`, `[SKU/...#estoque]`, `[Política de compra ativa (v1)]`, `[fichas-sku#...]` e `[documento.md]` sem slug não são citação de trecho e ficam como estão, sem marca: citam dados do ERP e da política que estão no contexto e são números, que pela ADR-0002 não vão ao Jev. Colchete misto conta só as partes com formato de id.
- **Tolerância ao redator**: colchetes lenticulares `【id】`, espaços e crases dentro do colchete e hífens U+2010 a U+2013 e U+2212 no id (viram `-`). Na afirmação, U+2010, U+2011 e espaços não separáveis viram hífen e espaço comuns.
- **Frase**: termina em `.`, `!` ou `?` seguidos de espaço (ponto de número e de caminho não termina), ou na quebra de linha. Leio "item de lista é uma frase" como "a quebra de linha termina a frase mesmo sem ponto"; um item com dois pontos finais vira duas frases, o que deixa a afirmação mais estreita. Citação logo depois do fim da frase (`dias. [id]`, `dias.[id]`) ou sozinha na linha seguinte fica com a frase anterior; sozinha no começo do texto fica com afirmação vazia, não vai ao Jev e sai `incerta`. A afirmação sai sem as citações de trecho, sem marcador de lista ou título, sem `*` e crases, sem parênteses que ficaram vazios e sem espaço antes da pontuação. Outros colchetes continuam nela.
- **Uma `Citacao` por (id, afirmação)**, na ordem do texto; a mesma citação repetida na frase conta uma vez. A marcação procura o veredito por (id, afirmação), então o mesmo id pode ser confirmado numa frase e marcado noutra. Colchete com alguma citação marcada é reescrito como `[id1; id2 - fonte inexistente]`, com os ids normalizados e colchete comum mesmo quando veio `【】`; colchete sem marca fica igual ao original.
- **`InMemoryDecisionModel`** ganhou `citacoes` (a `Escolha[Relacao]` por id do trecho citado, qualquer que seja a afirmação), `citacao_padrao` (`nao_trata` com confiança 1) e `falhar_citacoes`. `make_relacao(escolha, confianca=0.95)` em `tests/fakes.py`.
- **Termo novo** no `CONTEXT.md`: **Citação**, com os cinco vereditos.
- **Para o ticket 03**: verificar só a redação, antes de prefixar a confirmação da faixa média; `conferir_citacoes(redacao, montagem.trechos, decisao)` e `marcar_citacoes(redacao, verificacoes)`; na `DecisaoIndisponivel`, `decidir_vereditos(extrair_citacoes(redacao), {t.id for t in montagem.trechos}, [])`.
- **Testes**: `uv run pytest -q -m "not externo"` com 535 passando (eram 478). `-m "externo and not externo_llm"` com 8 passando, entre eles o novo `test_jev_real_confirma_o_prazo_do_contrato_e_nao_o_numero_trocado`.
