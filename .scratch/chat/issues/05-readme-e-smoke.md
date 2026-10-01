# 05: README, smoke e rodada dos casos pelo chat

**Status:** done
**Blocked by:** 04
**Spec:** `.scratch/chat/spec.md`

## What to build

Fecha o M5: smoke do `/chat` contra Postgres e o Jev real, README com o chat e os casos de `evals/casos.json` rodados pelo chat inteiro para ver o comportamento real (intenção, faixa, ação, SKUs).

## Acceptance criteria

- [x] Smoke `externo` em `tests/smoke/`: `POST /chat` de "Qual a situação do SKU TBC-BEGE-70140-01?" devolve `situacao_sku` com esse SKU, e o registro aparece em `GET /chat/registros`.
- [x] `scripts/rodar_casos_chat.py`: roda as 20 perguntas de `evals/casos.json` pelo `Copilot` com o Jev real e o redator configurado, e imprime por caso a intenção esperada e a escolhida, a confiança, a faixa, a ação e os SKUs. Resultado resumido num comentário deste ticket.
- [x] README: aviso do topo atualizado (M0-M5), variáveis novas, seção do chat com um exemplo real de `POST /chat` e de `GET /chat/registros`, módulos novos na estrutura.
- [x] Roadmap: M5 marcado como concluído, com a data.
- [x] `uv run pytest -q` verde (com `JEV_KEY`).

## Comments

**2026-09-30 (agente):** pronto, e o M5 fechado no roadmap. Decisões e desvios:

- **Smoke** (`tests/smoke/test_chat.py`): o teste novo é só `externo` e troca o redator pelo `RedatorSemLLM`, para não depender da Groq nem gastar tokens dela. Ele confere intenção, SKU, ficha e `redator == "sem_llm"`, e depois `GET /chat/registros?limite=1` com o mesmo `id` do `registro_id`, a pergunta, a intenção, os SKUs, o redator e a resposta. O smoke do ticket 03 com a Groq real continua (`externo` e `externo_llm`).
- **`scripts/rodar_casos_chat.py`** monta o `Copilot` com as mesmas peças do `POST /chat` (Postgres, Jev, redator do `.env`) e grava o registro de cada caso em `copilot.registros_decisao`, como o chat. Não grava arquivo em `evals/resultados/`: as respostas cruas ficam nos registros. Opções `--respostas` (imprime o texto) e `--pausa` (espera entre casos).
- **`--pausa` (fora do que o ticket pedia)**: na primeira rodada, 6 das 11 redações caíram no `RedatorSemLLM`. Diagnóstico: 429 da Groq por limite de tokens por minuto (plano gratuito, `openai/gpt-oss-120b`, 8.000 TPM); uma redação com trechos do corpus pede uns 3.100 tokens. A segunda rodada, com `--pausa 30`, teve as 11 redações pela Groq. O adapter não trata `retry-after` (fica para o M8), e com a queda o `RedatorSemLLM` abre com "Não há LLM configurado", o que confunde quando a chave existe (a observação no fim explica).
- **`docker-compose.yml`** passa a repassar `GROQ_API_KEY` ao app, como já fazia com `JEV_KEY`. O `.env` não entra na imagem (`.dockerignore`), então sem isso o chat no container sempre usaria o `RedatorSemLLM`.
- **README**: aviso M0-M5, variáveis da Groq, marcador `externo_llm` com `-m "not externo and not externo_llm"` para rodar sem custo, `POST /chat` e `GET /chat/registros` na tabela, seção do chat com o fluxo, exemplos reais dos dois endpoints (probabilidades do produto cortadas para as não nulas), a migration `0004_registros_decisao` e os limites conhecidos. Estrutura e grafo com as dependências novas do `ai` (`purchasing` no grafo, `catalog`, `ficha_sku` e `politica_compra` na lista) e a Groq.
- **Testes**: `uv run pytest -q -m "not externo"` com 440 passando; `-m externo` com 6; `-m externo_llm` com 2; `uv run pytest -q` com 446.

**Rodada dos casos pelo chat** (segunda rodada, `--pausa 30`, Jev `jev-1.13.0`, Groq `openai/gpt-oss-120b`, banco do seed):

- **Intenção**: 19/20. O erro é de novo o c11 ("Qual o lead time de verdade da Katrina?"): `situacao_sku` com 0,33, faixa baixa, esclarecimento (na primeira rodada, 0,45). Nas quatro medições do M5 esse caso ficou entre 0,31 e 0,49.
- **Faixas**: alta 16, média 3 (c06 0,69, c09 0,62, c14 0,65), baixa 1. **Ações**: `respondeu` 8, `fora_de_escopo` 5 (c16 a c20, todas com 1,00), `pediu_esclarecimento` 4, `confirmou_e_respondeu` 3.
- **SKUs**: c01 trouxe os 8 SKUs da toalha banho Conforto (sem cor na pergunta). c02 ("king percal 200") trouxe os 12 SKUs do Percal 200, porque o king só existe no Percal 300 e o filtro de tamanho que não casa é ignorado; a redação disse, corretamente, que não há king em percal 200. c06 ("o king size da Katrina") trouxe os dois king do Percal 300. Pediram o código: c03 (pano de prato, produto certo abaixo do limiar), c04 (45x70 não existe; candidato Toalha Rosto Conforto) e c05 (Veraneio, fora do catálogo; na primeira rodada o candidato citado era o Percal 200, na segunda nenhum). Ficaram sem SKU as sugestões c07 a c10, que responderam só com corpus e política.
- **Latência**: respostas em código de 0,4 a 0,8 s; redações de 2,9 a 6,4 s.
- **Redação** (o que fica para o M6 e o M8, sem mexer no prompt aqui):
  - Faz conta e comparação que o contexto não traz: no exemplo do README, compara a cobertura com teto e pisos e converte "30 dias" em "1,0 meses" e "20 dias" em "≈0,66 meses"; recomenda fornecedor ("Fornecedor recomendado (menor preço)").
  - Inventa citação: `[SKU/TBC-...]`, `[ TBC-AZUL-70140-07 ]`, `[Política de compra ativa (v1)]`, e no c14 usa colchetes `【】` no lugar de `[]`, o que atrapalha a verificação de citação do M6.
  - c06: ignorou a sugestão calculada (39 unidades do `JDCP-BRAN-KING-03`, zero do `JDCP-CHAM-KING-06`) e respondeu só com a ata do Natal 2024. Na primeira rodada ele apontou que a premissa "encalhou" não tem base nos trechos; na segunda, não.
  - c07 e c10 opinam ("a antecipação parece vantajosa", "a proposta é viável"), c08 manda o comprador calcular o volume. Não aprovam pedido, mas ficam perto da regra 7.
  - Acertos: c12 (aprovação de R$ 80 mil pela faixa 3), c13 (teto de 3 meses e exceção sazonal de até 5), c14 (contesta a premissa de que a Verdela atrasa) e c15 (sem exclusividade, com as datas dos trechos) responderam com a fonte certa.
  - Hífen não separável (U+2011) nos códigos de SKU de novo (c01 e o exemplo do README).

**2026-09-30 (revisão):** na revisão de código do M5, `scripts/rodar_casos_chat.py` deixou de repetir a composição do `get_copilot`: resolve o próprio `get_copilot` com `scripts/dependencias.py:resolver` e ganhou `--sem-llm`. A queda do redator por 429 agora abre com "O LLM que redige a resposta está indisponível no momento." (README atualizado). O smoke troca o redator com `lambda: RedatorSemLLM()`, porque o `RedatorSemLLM` agora recebe o motivo no construtor e o FastAPI leria esse parâmetro como query. Lista completa no ticket 03.
