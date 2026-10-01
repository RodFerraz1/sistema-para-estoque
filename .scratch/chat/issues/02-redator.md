# 02: Redator atrás de um port (Groq e sem LLM)

**Status:** done
**Blocked by:** nenhum
**Spec:** `.scratch/chat/spec.md` (seções "Contexto do redator" e "Redator")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O LLM entra só como redator: recebe a pergunta e um contexto já montado pelo código e devolve texto. Com `GROQ_API_KEY`, o `GroqRedator` chama a API compatível com a da OpenAI; sem chave, o `RedatorSemLLM` devolve os dados sem redação. O contexto é renderizado por uma função pura que marca os trechos do corpus como dado não confiável e já traz todo número calculado.

## Acceptance criteria

- [x] `src/ai/redator.py`: `Redator` (Protocol com `nome` e `redigir(pergunta, contexto) -> str`), `RedatorIndisponivel`, `INSTRUCOES_REDATOR` com as 7 regras da spec e `RedatorSemLLM`.
- [x] `src/ai/groq.py`: `GroqRedator` com `httpx2`, formato OpenAI de chat completions, `temperature` 0,2, `max_tokens` 2048, timeout de 30 s, sem tools. Erro HTTP, timeout e conteúdo vazio viram `RedatorIndisponivel`.
- [x] `src/ai/contexto.py`: `Montagem` (fichas, sugestões, parâmetros e versão da política, trechos classificados, conflitos, observações) e `renderizar_contexto(montagem) -> str` com as seções e formatos da spec (centavos em `R$ 1.234,56`, meses com vírgula, aviso antes dos trechos, trechos delimitados com id, documento, data e classificação).
- [x] `GROQ_API_KEY`, `GROQ_MODEL` (padrão `openai/gpt-oss-120b`) e `GROQ_BASE_URL` (padrão `https://api.groq.com/openai/v1`) em `Settings` e `.env.example`; `get_redator()` em `src/ai/dependencies.py`.
- [x] Marcador `externo_llm` no `pyproject.toml` e no `conftest.py` (pula sem `GROQ_API_KEY`).
- [x] Testes da spec para `contexto`, `GroqRedator` (`httpx2.MockTransport`) e `RedatorSemLLM`, e um `externo_llm` contra a Groq real.
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto. Decisões e desvios:

- **Sem chave, sem teste real**: não há `GROQ_API_KEY` no `.env`, então o `externo_llm` (`test_groq_real_redige_com_o_numero_do_contexto`) foi pulado e o `GroqRedator` só foi testado com `httpx2.MockTransport`. Risco não medido: o `openai/gpt-oss-120b` é modelo de raciocínio e, na Groq, o `max_tokens` de 2048 conta os tokens de raciocínio. Se o raciocínio consumir tudo, o conteúdo volta vazio, vira `RedatorIndisponivel` e o chat cai no `RedatorSemLLM`. Se isso aparecer com a chave, a saída é mandar `reasoning_effort` (M8).
- **Marcador `externo_llm` separado**: `-m "not externo"` não o exclui (o pytest compara o nome inteiro). Sem `GROQ_API_KEY` ele é pulado pelo `conftest.py`; com a chave, roda. O README (ticket 05) deve citar `-m "not externo and not externo_llm"` para rodar sem custo.
- **`pedido_minimo_reais` guarda reais, não centavos**: a spec diz que ele guarda centavos, mas a spec do M3 e o `purchasing` (`pedido_minimo_reais * 100`) tratam como reais inteiros. Só o `preco_unitario_reais` guarda centavos. O contexto não mostra pedido mínimo (não está na lista da spec), então nada muda aqui, mas quem for mostrar precisa saber.
- **`Montagem`** é um DTO Pydantic com `fichas`, `sugestoes`, `politica: PoliticaCompra | None` (parâmetros e versão juntos), `trechos`, `conflitos` e `observacoes`, todos opcionais.
- **Formatos**: reais `R$ 1.234,56`; inteiros com ponto de milhar (`1.234 unidades`); meses e unidades por mês com uma casa e vírgula (`1,0 mês`, `2,7 meses`); probabilidade de conflito com duas casas; data do trecho em `dd/mm/aaaa`.
- **Trechos**: cada um num bloco `<trecho id=... documento=... data=... classificacao=...>`. Tags `<trecho` e `</trecho` dentro do texto são escapadas para `&lt;`, para um trecho malicioso não fechar o próprio bloco. Depois do aviso fixo entra uma linha que explica `aceito` e `conflitante` (a spec não pede, mas sem ela o redator não sabe o que `conflitante` quer dizer).
- **`GroqRedator(chave, modelo, base_url, *, transport=None)`**: o `transport` existe para os testes. Além de erro HTTP, timeout e conteúdo vazio, falha de conexão e resposta fora do formato também viram `RedatorIndisponivel`. O texto volta sem espaços nas pontas. A mensagem do usuário leva `# Contexto` e depois `# Pergunta do comprador chefe`.
- **`get_redator()`** guarda o `GroqRedator` em `lru_cache`, como o `_jev`.
- **Testes**: `uv run pytest -q -m "not externo"` com 382 passando e 1 pulado (eram 350).

**2026-09-30 (revisão):** ajustes da revisão de código do M5 que tocam este ticket (lista completa no ticket 03):

- `GroqRedator` e `RedatorSemLLM` declaram o port (`class GroqRedator(Redator)`), como o `JevDecisionModel(DecisionModel)`. O `RedatorGravador` de `tests/fakes.py` também, com `nome` virando property.
- `Montagem` foi para `src/ai/schemas.py`.
- Contexto numa unidade só: cobertura, teto e pisos em meses, a unidade da cobertura no CONTEXT.md (os pisos, guardados em dias, são divididos por `DIAS_POR_MES`, como no `Inventory.abaixo_do_piso`). Com a política na montagem, a cobertura da ficha já sai comparada: "abaixo do piso de alerta da política", "entre o piso de alerta e o teto da política" ou "acima do teto da política". A comparação é com o piso de alerta porque é o piso da cobertura atual (o de reposição vale para a chegada da compra); no piso ainda não está abaixo, como no `abaixo_do_piso`. Risco pequeno: com uma casa decimal, cobertura e piso podem sair com o mesmo número (ex: 0,66 e 0,67 viram 0,7) e a frase dizer "abaixo"; a frase é a que vale.
- `RedatorSemLLM(motivo=SEM_LLM_CONFIGURADO)`: o texto de abertura agora é verdadeiro nos dois casos. Sem chave, "Não há LLM configurado para redigir a resposta."; na queda do redator, o `Copilot` usa `LLM_INDISPONIVEL`, "O LLM que redige a resposta está indisponível no momento.".
