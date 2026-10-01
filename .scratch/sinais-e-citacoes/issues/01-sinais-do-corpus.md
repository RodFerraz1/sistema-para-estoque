# 01: Sinais do corpus para a sugestão de pedido

**Status:** done
**Blocked by:** M5 concluído
**Spec:** `.scratch/sinais-e-citacoes/spec.md` (seção "Sinais do corpus" e "Endpoint")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

Para o fornecedor e o produto de uma sugestão de pedido, o código busca no corpus e pergunta ao Jev, trecho a trecho, se há relato de atraso do fornecedor, de venda forte por época e de encalhe. As respostas acima do limiar viram sinais com os trechos de origem, sem mexer na quantidade. Os limiares saem de uma avaliação contra o Jev real. `GET /skus/{sku_code}/sugestao-compra/sinais` expõe os sinais.

## Acceptance criteria

- [x] `DecisionModel.avaliar_sinais` com as três perguntas da spec, no `JevDecisionModel` e no `InMemoryDecisionModel`.
- [x] `BuscaContexto.buscar` com `com_conflitos` (padrão `True`).
- [x] `src/ai/sinais.py`: `SinaisCorpus.para_sugestao` e `para_sugestoes` (um cálculo por par fornecedor e produto), `K_SINAIS`, `MAX_TRECHOS_SINAIS`, `LIMIARES_SINAIS`; `SinalCorpus`, `ProdutoDoSinal`, `AvaliacaoSinais` e `SugestaoComSinais` nos schemas.
- [x] `evals/sinais.json` rotulado antes de rodar; `scripts/avaliar_sinais.py` (com `--de-arquivo`) rodado contra o Jev real; respostas cruas em `evals/resultados/`; resultado e limiares escolhidos num comentário deste ticket. O teste que confere os ids de `evals/` cobre o arquivo novo.
- [x] `GET /skus/{sku_code}/sugestao-compra/sinais` (404, 503, lista vazia sem fornecedor).
- [x] Testes da spec e um `externo` do `avaliar_sinais`.
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Avaliação** (`evals/sinais.json`, 22 casos rotulados antes de rodar, cada um com o `motivo` do rótulo): 3 positivos de atraso, 4 de venda por época e 4 de encalhe; casos de fornecedor trocado (s04 e s05: atraso da Katrina perguntado para a Malha Fina e para a Verdela), de produto trocado (s13, s18 e s22: Natal do jogo de cama para pano de prato, Veraneio para toalha e para toalha de mesa) e armadilhas (s08: quem atrasou o pedido de Natal foi o atacadista; s14: fila da fábrica por época não é venda; s19: encalhe só como risco hipotético). O produto vai com `nome` e `categoria` do seed, e o fornecedor com o nome do ERP ("Katrina Têxtil"). Deixei fora a justificativa do Natal king size, porque o item "sem oscilação sazonal fora do Natal" deixava o rótulo de venda por época ambíguo.
- **Resultado** (`evals/resultados/sinais-2026-09-30.json`, `jev-1.13.0`, 22 requests, latência mediana 0,27 s e máxima 0,38 s; recalcula com `uv run python -m scripts.avaliar_sinais --de-arquivo evals/resultados/sinais-2026-09-30.json`):
  - `atraso_do_fornecedor`: positivos de 0,94 a 0,98; o negativo mais alto é o s07 (lead time da Malha Fina, "observado 20-25 dias para 20 prometidos", 0,67), e o resto fica em 0,13 ou menos. 22/22 de 0,70 a 0,90. Fornecedor trocado: 0,09 e 0,13.
  - `demanda_sazonal`: positivos 0,98, 0,94, 0,82 e 0,58 (s11, "venda de dezembro cumpriu 108% do previsto", que o Jev não leu como venda forte por época). Negativos altos: s14 (fila da fábrica, 0,69), s19 (0,63), s16 (0,61), s08 (0,57). 21/22 de 0,70 a 0,80.
  - `encalhe`: positivos 0,98, 0,80, 0,79 e 0,65 (percal 200 king com "histórico de estoque parado"); o negativo mais alto é o risco hipotético do s19 (0,48). 22/22 de 0,50 a 0,60. Produto trocado: 0,27 e 0,15.
  - **`LIMIARES_SINAIS = LimiaresSinais(atraso_do_fornecedor=0.90, demanda_sazonal=0.80, encalhe=0.60)`**, pela regra da spec (mais acertos; no empate, o mais alto).
- **Risco registrado**: a regra do empate pelo mais alto escolhe o limiar com a menor folga para os positivos. No atraso, 0,90 fica a 0,04 do positivo mais baixo (0,94), embora qualquer valor de 0,70 a 0,90 acerte tudo. Fora da amostra, a justificativa do Natal king size ("lead time real da Katrina passou de 45 pra 68 dias", atraso explícito) deu 0,86 para Katrina e toalha e fica fora do sinal em 0,90. Não mudei o limiar por um caso sem rótulo visto depois de rodar (mesma regra do spike); fica como primeiro candidato para o gabarito do M8. Na venda por época, 0,80 fica a 0,02 do s12 (0,82). A amostra é pequena (3 ou 4 positivos por tipo).
- **Sugestão sem fornecedor** no código atual inclui a de quantidade zero por estar acima do ponto de reposição (o `purchasing` só põe fornecedor quando há compra), não só SKU novo, sem giro ou sem fornecedor como a spec lista. A regra implementada é a da spec, "sem fornecedor, sem sinal", então no seed só 34 dos 80 SKUs podem ter sinais.
- **Ordem**: sinais na ordem de `TipoSinal` (atraso, venda por época, encalhe). Um trecho vira sinal quando a probabilidade passa do limiar (estrito, como os `LIMIARES` da busca), e a avaliação usa a mesma comparação. Os trechos que vão ao Jev são os `aceito` e `conflitante` ordenados só por similaridade (a spec diz "por similaridade"; o `Copilot` põe aceitos antes de conflitantes, mas aqui a classificação não muda a pergunta). Sem trecho aceito ou conflitante, `avaliar_sinais` não é chamado.
- **`para_sugestoes`** devolve uma chave por SKU, na ordem dos pares, com lista vazia para sugestão sem fornecedor. O cache é por `(nome do fornecedor, ProdutoDoSinal)`, que é hashable por ser frozen. `DecisaoIndisponivel` propaga: tratar a queda nos sinais como observação é do ticket 03.
- **`SinaisCorpus(busca, decisao)`** em `src/ai/sinais.py`, montado por `get_sinais_corpus` em `src/ai/dependencies.py`. `TipoSinal` é um `Literal` em `src/ai/schemas.py`, reaproveitado pelo DTO HTTP e pelo script. `LimiaresSinais` é um dataclass como o `Limiares` da busca.
- **`InMemoryDecisionModel`** ganhou `sinais` (por trecho), `sinais_padrao` e `falhar_sinais`, com a mesma regra dos trechos: o que não foi configurado vale 0, qualquer que seja o fornecedor ou o produto.
- **Endpoint** `GET /skus/{sku_code}/sugestao-compra/sinais` com `SinalCorpusResponse` em `src/api/schemas.py` e `sinal_to_response` em `src/api/conversores.py` (o ticket 03 reaproveita). Como no `/chat`, o Jev é dependência da rota: sem `JEV_KEY` a resposta é 503 antes de olhar o SKU, então 404 e lista vazia só saem com o Jev configurado. SKU sem snapshot de estoque dá 500, como no `/sugestao-compra`.
- **Saída real** (Postgres do seed, Jev real): `TBC-BEGE-70140-01` (Katrina) traz atraso com `fornecedores/katrina-textil.md#lead-time` e os riscos consolidados da revisão Q1 (0,96); `JDCP-BRAN-QUEEN-02` (Verdela, percal 300) e `CB-OFF--QUEEN-09` (Verdela, colcha) trazem encalhe com os trechos da Veraneio (0,99 e 0,95); `PM-AZUL-3040-02` e `TDMR-OFF--160270-04` (Malha Fina) vêm sem sinal. Para a toalha da Katrina, a revisão Q1 da Katrina (0,98 na avaliação) não entra nos 15 trechos mais parecidos da busca focada, e a busca descarta 7 dos 15 por relevância: o recall dos sinais depende da busca, não só do Jev.
- **Fora do escopo, sem mexer**: README (endpoint novo e aviso de M6) fica para o ticket 03, que fecha o milestone.
- **Testes**: `uv run pytest -q -m "not externo"` com 478 passando (eram 447). `-m "externo and not externo_llm"` com 7 passando, entre eles os novos `test_jev_real_ve_o_atraso_da_katrina_so_para_a_katrina` e o smoke `tests/smoke/test_sinais.py` (sinais de `TBC-BEGE-70140-01` trazem `atraso_do_fornecedor`).

**2026-09-30 (revisão):** ajustes da revisão de código do M6:

1. Tipo de sinal num lugar só: `AvaliacaoSinais.probabilidades: dict[TipoSinal, Probabilidade]` (validada: uma por tipo), `LIMIARES_SINAIS: dict[TipoSinal, float]` (sem o dataclass `LimiaresSinais`) e as mensagens no mapa `_MENSAGENS` de `sinais.py`, no estilo de `_VEREDITOS` e `_MARCAS`. O `JevDecisionModel` e o `InMemoryDecisionModel` montam as probabilidades percorrendo `get_args(TipoSinal)`; `ProbabilidadesSinais` saiu (a configuração do in-memory é `Mapping[TipoSinal, float]`). `PERGUNTAS_SINAIS` continua declarado pergunta a pergunta. Um tipo novo pede o `Literal`, o limiar, a mensagem e a pergunta, e o teste `test_todo_tipo_de_sinal_tem_limiar_e_mensagem` percorre os tipos.
2. `SinaisCorpus.para_sugestoes(pares) -> SinaisDasSugestoes` (o antigo `para_sugestoes_com_trechos`; o `para_sugestoes` que só devolvia o dicionário saiu). `SinaisDasSugestoes.trechos` virou `trechos_de_origem`, e o retorno interno de `_sinais` virou `_SinaisDoPar` (`sinais`, `avaliados`).
3. `scripts/avaliar_sinais.py` lê `probabilidades[tipo]` e imprime `LIMIARES_SINAIS = {...}`. As respostas gravadas em `evals/resultados/sinais-2026-09-30.json` foram convertidas para o formato novo da `AvaliacaoSinais` (os valores não mudaram); `--de-arquivo` dá os mesmos limiares.
