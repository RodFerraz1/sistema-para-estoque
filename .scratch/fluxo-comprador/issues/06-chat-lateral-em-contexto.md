# 06: Chat lateral em contexto

**What to build:** o chat deixa de ser uma tela separada e vira um painel lateral no painel de alertas, na tela do SKU e na política. Na tela do SKU, o chat já sabe de qual SKU se trata. "Por que está acabando?" responde sobre esse SKU, e uma pergunta que cita outro produto responde sobre o citado.

**Blocked by:** 04

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "`ai` (chat)", "Esquema", "API" e "UI")

- [x] `Copilot.responder` aceita `sku_em_contexto` opcional. Para as intenções `situacao_sku` e `sugestao_compra` sem SKU identificado na pergunta, usa o SKU em contexto, marcado com origem `contexto`. Produto citado tem precedência, e as outras intenções ignoram o contexto. A intenção continua com o Jev (ADR-0002).
- [x] O registro de decisão grava `sku_em_contexto` (migration). Os scripts de avaliação continuam funcionando sem contexto.
- [x] `POST /chat` aceita `sku_code` opcional e responde 404 para SKU desconhecido.
- [x] Um único componente de chat lateral, montado pelo painel, pela tela do SKU e pela política:
  - mostra qual SKU está em contexto;
  - abre e fecha pelo cabeçalho e abre em tela cheia no celular;
  - reaproveita a renderização atual de resposta, citações, fichas e sugestões.
- [x] `chat.html` sai e a navegação do comprador fica Painel e Política, mais o botão do chat.
- [x] Testes HTTP com Jev fake cobrem: pergunta sem produto usa o contexto, produto citado tem precedência, `politica_ou_fornecedor` ignora o contexto, o registro grava o contexto e o 404. O teste de UI continua sem chamadas órfãs.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões:

- **Regra do contexto** (ADR-0002: a intenção segue com o Jev, a regra é do código): `Copilot.responder(pergunta, sku_em_contexto=None)`. Para `situacao_sku` e `sugestao_compra`, se `identificar_skus` não acha SKU (nem por código, nem pelo produto do Jev) e há SKU em contexto, a identificação vira `do_contexto(sku)`, com origem nova `contexto`. As outras intenções nem olham o contexto. Quando a origem é `contexto`, a montagem ganha uma observação para o redator ("a pergunta não cita produto e o comprador está na tela do SKU X"), para a resposta não soar como se o SKU tivesse sido citado.
- **Registro**: `RegistroDecisao.sku_em_contexto` (opcional, padrão nulo, então os scripts de avaliação seguem sem contexto) e migration `0012_sku_em_contexto` (downgrade testado). O registro grava o contexto mesmo quando a pergunta cita outro produto, para a auditoria saber de que tela veio. `GET /chat/registros` devolve o campo.
- **API**: `POST /chat` aceita `sku_code`; SKU desconhecido responde 404 antes de chamar o Jev, sem registro.
- **UI**: `chat.html` saiu e `chat.js` virou o componente `montarChat(sku)`, reaproveitando a renderização de resposta, citações, fichas, sugestões e trechos. Painel, tela do SKU e política montam o chat. Cabeçalho com Painel, Política e o botão "Chat" (`aria-expanded`). O chat é um `aside` fixo à direita (460 px; em telas de 1100 px ou mais o conteúdo abre espaço; abaixo disso ele cobre a página, e no celular ocupa a tela toda). Mostra a faixa "SKU em contexto: X" ou "Sem SKU em contexto". Fecha com o botão ou Esc. Nesta tela a resposta mais nova fica embaixo, perto do campo.
- **Verificação manual** (Chrome, Jev e Claude reais): na tela do `JDCP-ROSA-SOLTEIRO-10`, "Por que está acabando?" respondeu com a ficha desse SKU. Ficou um registro de decisão desta pergunta no banco local.
- `uv run pytest -q` com Postgres: 782 passando. Pyright sem erro novo.
