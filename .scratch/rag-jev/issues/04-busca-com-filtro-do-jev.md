# 04: Busca com filtro do Jev end-to-end

**Status:** done
**Blocked by:** 02 (Spike do Jev, precisa ter passado no gate), 03 (Ingestão do corpus no pgvector)
**Spec:** `.scratch/rag-jev/spec.md`
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O comprador pesquisa em `GET /rag/busca?q=...&k=...` e recebe os trechos mais parecidos, cada um classificado como `aceito`, `conflitante` ou `descartado` a partir das quatro respostas do Jev e dos limiares do spike. O Jev entra atrás do port `DecisionModel`, com um adapter in-memory para os testes. Conflito entre trechos fica para o 05.

## Acceptance criteria

- [x] Port `DecisionModel` com `avaliar_trechos(pergunta, trechos) -> list[AvaliacaoTrecho]` e a exceção `DecisaoIndisponivel`.
- [x] `JevDecisionModel` com as quatro perguntas da spec, na redação escolhida no spike, um request por trecho, até 8 em paralelo. `modelo` vem da resposta. Erro do SDK depois das retentativas vira `DecisaoIndisponivel`.
- [x] `JEV_MODEL` com padrão `jev-1.13.0` em `Settings` e `.env.example`.
- [x] `InMemoryDecisionModel` configurável por trecho, com padrão e com modo de falha.
- [x] `BuscaContexto.buscar(pergunta, k)` com `LIMIARES` (valores do `spike-resultado.md`) e a classificação na ordem da spec. `ResultadoBusca` ordenado por classificação e depois por similaridade, com `conflitos` vazio por enquanto.
- [x] `GET /rag/busca`: 422 para `q` vazio ou acima de 500 caracteres e para `k` fora de 1 a 40 (padrão 30, decisão do ticket 03); 503 para `DecisaoIndisponivel`; 200 com listas vazias quando o corpus não foi ingerido.
- [x] Testes: uma regra de classificação por teste, precedência das regras, valores no limiar, falha do Jev (com `InMemoryDecisionModel`); `JevDecisionModel` com cliente TypeSafe falso (state, mapeamento das respostas, `modelo`, erro); teste `externo` contra o Jev real, pulado sem `JEV_KEY`; HTTP feliz, 422, 503 e corpus vazio.
- [x] Marcador `externo` registrado no `pyproject.toml`.
- [x] `uv run pytest` verde.

## Comments

**2026-09-30 (agente):** bloqueado pelo resultado do spike (`.scratch/rag-jev/spike-resultado.md`). O ticket 03 mudou o `k` padrão da busca para 30 (recall@30 de 0,92), então o endpoint aceita `k` de 1 a 40.

**2026-09-30 (agente):** a rodada 2 do spike também não passou, só pela relevância (ver `.scratch/rag-jev/spike-resultado.md`). Se a ADR-0002 continuar, este ticket muda em dois pontos: `tenta_instruir` vira uma pergunta separada sobre o trecho sozinho (dá para calcular uma vez por trecho), e os `Noul` levam os criteria da rodada 2 (`scripts/spike_jev.py`, redação PT).

**2026-09-30 (agente):** desbloqueado. O gate também não passou com o gabarito cego, e o dev decidiu manter a ADR-0002 inteira (registrado na ADR e em `.scratch/rag-jev/spike-resultado.md`). Valem os dois pontos do comentário anterior, a redação PT e os limiares da seção "Gabarito cego" do resultado do spike: injeção 0,50, t_rel 0,55, t_evid 0,15, `contradiz_premissa` 0,85 e conflito 0,10.

**2026-09-30 (agente):** pronto. Desvios em relação à spec e aos critérios acima:

- O port recebe `Sequence[Trecho]`, e não `list[Trecho]`, porque a busca passa `list[TrechoRecuperado]` e `list` é invariante.
- São 2 requests por trecho, e não 1: os 3 `Noul` com a pergunta e o trecho no state, e o `tenta_instruir` com o trecho sozinho, como na rodada 2 do spike.
- O `InMemoryDecisionModel` recebe probabilidades parciais por trecho (`Probabilidades`) em vez de `AvaliacaoTrecho`. O que não foi configurado vem de `padrao` ou vale 0.
- O 503 sai de um exception handler registrado em `create_app()`, porque `get_decision_model` também lança `DecisaoIndisponivel` quando não há `JEV_KEY`. Sem a chave, `/rag/busca` dá 503 mesmo com o corpus vazio.
- O cliente do Jev (`criar_cliente` em `src/ai/jev.py`) usa timeout de conexão de 2 s. Com 8 conexões em paralelo, parte dos handshakes TLS com a API travava até o timeout total de 10 s, e o teste `externo` falhava em cerca de metade das execuções. `httpx2` passou a ser dependência declarada.
