# 01: Entendimento da pergunta e identificação dos SKUs

**Status:** done
**Blocked by:** nenhum
**Spec:** `.scratch/chat/spec.md` (seções "Entendimento da pergunta", "Identificação dos SKUs" e "Avaliação do entendimento contra o Jev real")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O Jev responde, num request, a intenção da pergunta e o produto do catálogo que ela cita. O código acha o código de SKU escrito na pergunta ou, sem código, usa o produto do Jev e estreita pelos SKUs com a cor e o tamanho citados. A escolha do produto é medida contra o Jev real antes de ser usada, e o limiar sai dessa medida.

## Acceptance criteria

- [x] `Intencao`, `Escolha`, `Entendimento` e `ProdutoCatalogo` em `src/ai/schemas.py`, como na spec.
- [x] `DecisionModel.entender_pergunta(pergunta, produtos) -> Entendimento`, implementado no `JevDecisionModel` (intenção com a redação PT exata do spike, produto com uma opção por produto mais `nenhum`, um request só) e no `InMemoryDecisionModel` (configurável por pergunta, com padrão e modo de falha).
- [x] `Catalog.listar_skus()`.
- [x] `src/ai/identificacao.py` com `produtos_do_catalogo`, `identificar_skus`, `Identificacao`, `LIMIAR_PRODUTO` e `MAX_SKUS_POR_RESPOSTA`, com as regras da spec.
- [x] `produtos_aceitos` em cada caso de `evals/casos.json`, escrito antes de rodar o script. O teste que confere os ids de `evals/` passa a conferir também que todo produto citado existe no catálogo do seed (ou é `nenhum`).
- [x] `scripts/avaliar_entendimento.py` (com `--de-arquivo`) rodado contra o Jev real (`JEV_KEY` está no `.env`), com as respostas cruas em `evals/resultados/entendimento-<data>.json`. Resultado (acerto da intenção, acerto do produto, varredura do limiar) registrado num comentário deste ticket, e `LIMIAR_PRODUTO` fixado pela regra da spec.
- [x] Testes da spec para `identificacao` e `entender_pergunta` (cliente falso e um `externo`).
- [x] `uv run pytest -q -m "not externo"` verde e os `externo` novos passando.

## Comments

**2026-09-30 (agente):** implementado com o dev AFK. Decisões e desvios:

- **Rótulos** (`produtos_aceitos`, escritos antes de rodar): c02 aceita Percal 200 e Percal 300 (a pergunta diz "percal 200 fios" e "king", mas no catálogo king só existe no Percal 300); c06 e c09 ("o king size da Katrina", "o king do Natal") aceitam Percal 200, Percal 300 e `nenhum` (citam um tamanho, não um produto; o corpus fala de percal 200 king, o catálogo só tem king no 300); c05 (linha Veraneio, que não está no catálogo) e c08 (colcha *nova* da Verdela) só `nenhum`; c07 aceita as duas toalhas Conforto; c10 aceita as duas toalhas de mesa; c11 a c20 só `nenhum` (c15 cita a categoria felpudo, não um produto).
- **Resultado** (`evals/resultados/entendimento-2026-09-30.json`, `jev-1.13.0`, 20 requests, latência mediana 0,26 s e máxima 0,46 s):
  - Intenção: 19/20. Único erro: c11 ("Qual o lead time de verdade da Katrina?") veio `situacao_sku` com confiança 0,31, o mesmo caso e a mesma faixa do spike. Com `FAIXAS.media = 0,50` ele cai em esclarecimento.
  - Produto: 18/20. Erros: c04 ("toalha de rosto 45x70", o tamanho do catálogo é 48x80) veio `nenhum` com 0,63, o que leva a um esclarecimento, e não a SKU errado; c08 ("colcha nova" da Verdela) veio `Colcha Bouti` com 0,57.
  - Varredura (produtos usados certos/errados): 0,30 a 0,45: 6/1; 0,50 e 0,55: 5/1; 0,60 e 0,65: 3/0; 0,70 a 0,95: 2/0.
  - **`LIMIAR_PRODUTO = 0,60`**, o menor limiar sem produto errado, pela regra da spec.
- **Risco registrado**: a margem é pequena (o produto errado teve 0,57) e a amostra também (só 7 dos 20 casos escolhem um produto). Em 0,60 três escolhas certas ficam abaixo do limiar: c03 (0,56), c10 (0,59) e c07 (0,45). Esses casos viram esclarecimento com `candidatos`, o que é mais seguro do que responder sobre o SKU errado. A recalibração com o registro fica para o M8.
- **Varredura sobre os 20 casos**, e não só nos de intenção com SKU: é mais conservador, porque uma intenção mal roteada também usaria o produto.
- **`Escolha` é genérica** (`Escolha[Intencao]` na intenção e `Escolha[str]` no produto), em vez de `escolha: str` com um validador. O Pydantic valida o `Literal` e quem consome recebe o tipo estreito.
- **`NENHUM_PRODUTO = "nenhum"`** em `src/ai/schemas.py`, usado pelo adapter do Jev, pela identificação e pelo script.
- **`Identificacao.total_skus`** (campo a mais que a spec): conta os SKUs antes do corte em `MAX_SKUS_POR_RESPOSTA`, para o ticket 03 montar a observação de lista cortada (`total_skus > len(skus)`).
- **Código na pergunta** também casa sem acento (`lt-azul-unico-03` acha `LT-AZUL-ÚNICO-03`): pergunta e códigos são comparados sem acento e sem caixa, e "palavra inteira" quer dizer sem letra, dígito ou hífen colado dos dois lados. Os SKUs saem na ordem do catálogo, não na da pergunta.
- **`produtos_do_catalogo`**: produtos na ordem do primeiro `sku_code`, e cores e tamanhos na ordem em que aparecem nos SKUs ordenados por código. `prefixo` é o primeiro segmento do código. No seed, `JDCP` (Percal 200 e 300) e `TDMR` (toalha de mesa retangular e redonda) aparecem em dois produtos cada. Quem separa esses pares são as cores e os tamanhos da descrição.
- **Candidatos** só contam nomes que estão no catálogo, até 3, com probabilidade >= 0,15 (`PROBABILIDADE_MINIMA_CANDIDATO` e `MAX_CANDIDATOS` em `identificacao.py`).
- **`InMemoryDecisionModel`**: aceita `entendimentos` por pergunta, `entendimento_padrao` (por padrão `fora_de_escopo` e `nenhum` com confiança 1) e `falhar_entendimento`. `make_entendimento` em `tests/fakes.py` serve para os testes do ticket 03.
- **Testes**: `uv run pytest -q -m "not externo"` com 350 passando (eram 315). `-m externo` com 3 passando, entre eles o novo `test_jev_real_entende_a_situacao_da_toalha_conforto_branca`.
