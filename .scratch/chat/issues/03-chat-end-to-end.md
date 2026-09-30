# 03: `POST /chat` end-to-end com roteamento por confiança

**Status:** done
**Blocked by:** 01, 02
**Spec:** `.scratch/chat/spec.md` (seções "Faixas de confiança e roteamento", "Resposta do Copilot" e "Endpoints")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O comprador pergunta em `POST /chat` e recebe texto. O `Copilot` pede o entendimento ao Jev, decide pela faixa de confiança da intenção, identifica os SKUs, monta os dados pela intenção (fichas, sugestões, busca no corpus), renderiza o contexto e chama o redator. Esclarecimento e fora de escopo são respostas feitas em código, sem redator. A queda do redator cai no `RedatorSemLLM`.

## Acceptance criteria

- [x] `src/ai/chat.py`: `Copilot.responder(pergunta) -> RespostaCopilot`, `FAIXAS`, `MAX_TRECHOS_NO_CONTEXTO`, textos de confirmação, esclarecimento e fora de escopo como na spec.
- [x] Montagem por intenção como na spec: fichas e política para `situacao_sku`; sugestões, política e busca para `sugestao_compra`; busca para `politica_ou_fornecedor`. Só trechos `aceito` e `conflitante` chegam ao contexto, até o máximo.
- [x] Faixa média prefixa a confirmação à redação; faixa baixa pede esclarecimento com as duas intenções mais prováveis; SKU não identificado pede esclarecimento com os candidatos.
- [x] `RedatorIndisponivel` cai no `RedatorSemLLM` com a observação; `DecisaoIndisponivel` vira 503.
- [x] `POST /chat` (`src/api/chat.py`) com DTOs HTTP, reaproveitando os conversores de ficha, sugestão e trecho. Router registrado em `create_app()`. `registro_id` pode ficar nulo até o ticket 04.
- [x] Testes da spec para o `Copilot` (adapters em memória) e HTTP (feliz, 422, 503).
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto. Decisões e desvios:

- **`Copilot(decisao, catalog, ficha_sku, purchasing, politicas, busca, redator)`** em `src/ai/chat.py`, montado por `get_copilot()` em `src/ai/dependencies.py`. `RespostaCopilot` fica em `chat.py`, com `registro_id: UUID | None = None` até o ticket 04. `Faixa` e `Acao` são `Literal` exportados de `chat.py`.
- **Ordem do roteamento**: faixa baixa pede esclarecimento antes de olhar a intenção, então um `fora_de_escopo` com confiança baixa também vira esclarecimento. `fora_de_escopo` em faixa média é resposta fixa, sem a confirmação (a confirmação só prefixa redação).
- **Esclarecimento de SKU em faixa média** também não leva a confirmação: é resposta em código, com `acao` `pediu_esclarecimento`, e a `identificacao` (com os candidatos) vai na resposta. Candidatos citados como "A", "A ou B" ou "A, B ou C", depois do texto da spec.
- **Esclarecimento de intenção**: as duas mais prováveis saem das quatro intenções ordenadas pela probabilidade da `Choice` (intenção ausente vale 0; empate fica na ordem do `Literal`).
- **Observações da montagem** feitas em código: lista cortada ("A pergunta corresponde a N SKUs; os dados abaixo trazem só os 12 primeiros."), SKU sem estoque ("O SKU X não tem registro de estoque no ERP.", no lugar do erro 500 do `/skus`), sugestão sem SKU (a quantidade depende de um SKU do catálogo) e queda do redator (texto da spec). SKU que o ERP não acha mais entre a listagem e a leitura é pulado sem observação.
- **Trechos**: só `aceito` e `conflitante`, aceitos primeiro e depois conflitantes, cada grupo por similaridade, até `MAX_TRECHOS_NO_CONTEXTO = 10`. A ordem é refeita no `Copilot` em vez de depender da ordem da `BuscaContexto`. Só ficam os conflitos em que os dois trechos foram ao contexto.
- **Conversores HTTP** de ficha, fornecedor, sugestão e trecho saíram de `src/api/skus.py` e `src/api/rag.py` para `src/api/conversores.py` (públicos, sem `_`). DTOs novos em `src/api/schemas.py`: `PerguntaChatRequest`, `EscolhaResponse`, `EntendimentoResponse`, `IdentificacaoResponse` e `RespostaChatResponse`. `OrigemIdentificacao` virou um alias nomeado em `identificacao.py` para o DTO HTTP reaproveitar.
- **`RedatorGravador`** em `tests/fakes.py` (guarda `(pergunta, contexto)` de cada chamada, com modo de falha). Os testes HTTP do `/chat` sempre trocam o redator, porque com `GROQ_API_KEY` no `.env` o `get_redator()` devolve o `GroqRedator`.
- **Smoke com Jev e Groq reais** (a chave da Groq chegou durante o ticket): `tests/smoke/test_chat.py`, marcadores `smoke`, `externo` e `externo_llm`, passando. Ele confere intenção, SKU e redator `groq:`, não o texto. O ticket 05 pode estender este arquivo com o registro.
- **O que a saída real mostrou** (Jev `jev-1.13.0`, Groq `openai/gpt-oss-120b`, banco do seed):
  - "Qual a situação do SKU TBC-BEGE-70140-01?": `situacao_sku` 1,00, SKU por código, 3,4 s. A redação trouxe os números do contexto certos, mas também **comparou a cobertura com o teto e o piso** ("30 dias (≈ 1,0 mês)", "dentro da faixa aceitável"), **escolheu um fornecedor** ("Katrina Têxtil é a opção preferencial") e inventou uma citação `[SKU/TBC-BEGE-70140-01]`. Isso fere as regras 2 e 4 do redator. Também usou hífen não separável (U+2011) no código do SKU num título, e por isso o smoke não compara o texto. Fica para o M6 (verificação de citação) e o M8 (instruções e `reasoning_effort`).
  - "Quanto devo comprar da toalha banho conforto bege?": `sugestao_compra` 0,98, produto do Jev estreitado para os dois SKUs bege (400 g e 450 g), dois trechos aceitos, 5,2 s. A redação citou só uma sugestão (261 unidades, alerta de pedido mínimo) e não falou do outro SKU.
  - "Qual o lead time da Katrina?": `politica_ou_fornecedor` com 0,49, faixa baixa, esclarecimento em 0,3 s (o mesmo caso limítrofe do ticket 01). A frase fica com "ou" duplo ("saber da política de compra ou de um fornecedor ou ver a situação de um SKU"), porque a descrição da spec já tem "ou". Mantive o texto da spec.
  - "Quem ganhou o jogo ontem?": `fora_de_escopo` 1,00, resposta fixa em 0,3 s.
- **Para o ticket 04**: todo caminho de `responder` termina num `return RespostaCopilot(...)` (esclarecimento de intenção, fora de escopo, esclarecimento de SKU e redação). O jeito mais simples de gravar um registro por pergunta é renomear o corpo atual para um `_decidir` e, em `responder`, medir a duração, gravar e devolver `resposta.model_copy(update={"registro_id": ...})`. `DecisaoIndisponivel` sai antes, então já fica sem registro.
- **Testes**: `uv run pytest -q -m "not externo"` com 414 passando (eram 382 e 1 pulado; o `externo_llm` da Groq agora roda com a chave). `-m externo` com 5 passando.
