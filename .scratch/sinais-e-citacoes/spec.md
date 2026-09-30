---
Status: ready-for-agent
Escopo: M6 do roadmap (sugestão com sinais do corpus e citações verificadas)
Vocabulário: ver /CONTEXT.md
Decisões arquiteturais base: /docs/adr/0002-jev-decide-codigo-executa-llm-redige.md
Depende de: M5 (`.scratch/chat/spec.md`)
Referência do Jev: https://docs.typesafe.ai/llms.txt (receita base da verificação: https://docs.typesafe.ai/cookbooks/citation_check.md)
Origem: decisões do agente em 2026-09-30, com o dev AFK e autonomia total delegada
---

# Spec 06 - Sinais do corpus na sugestão e citações verificadas

## Problem Statement

Com o M5, o comprador pede uma sugestão no chat e recebe a quantidade calculada pela política junto com os trechos que a busca achou para a pergunta dele. Duas lacunas continuam.

A primeira: o que o corpus sabe sobre o fornecedor e o produto da sugestão só aparece se a pergunta do comprador puxar o assunto. Se ele pergunta "quanto compro do TBC-BEGE-70140-01?", a resposta não lembra que a Katrina atrasa há três trimestres, nem que uma linha parecida já encalhou. O M3 alerta o que o ERP mostra (lead time observado acima do contratado), mas não o que as reuniões e retrospectivas registram.

A segunda: o redator cita trechos entre colchetes, mas ninguém confere se o trecho citado sustenta a frase. Um LLM pode citar um trecho real para uma afirmação que o trecho não faz, ou inventar um id. Com a precisão da busca em 0,34 (risco aceito na ADR-0002), o redator recebe muitos trechos que sobram, e o risco de citação errada é maior.

## Solution

1. **Sinais do corpus**: para cada par (fornecedor sugerido, produto) de uma sugestão, o código faz uma busca focada no corpus e pergunta ao Jev, trecho a trecho, três coisas: se relata atraso desse fornecedor, se relata venda forte do produto numa época do ano e se relata encalhe do produto. O código transforma as respostas acima do limiar em sinais com os trechos de origem. Os sinais acompanham a sugestão e nunca alteram a quantidade.
2. **Verificação de citações**: depois da redação, o código extrai cada citação `[id]` com a frase que a contém. Id que não estava no contexto é marcado como fonte inexistente, sem chamar o Jev. Os demais vão ao Jev com uma `Choice` (sustenta, contradiz, não trata), e o código marca no texto toda citação que não foi confirmada com confiança.
3. **Chat**: a intenção `sugestao_compra` passa a trazer os sinais de cada sugestão no contexto do redator e na resposta, e toda resposta redigida por LLM passa pela verificação. O registro de decisão guarda os sinais e as verificações.
4. **Endpoint** `GET /skus/{sku_code}/sugestao-compra/sinais` devolve os sinais da sugestão de um SKU (o M7 usa a mesma função para priorizar a fila).

## User Stories

### Comprador chefe

1. Como comprador chefe, quero que a sugestão de compra me avise quando os documentos contam atraso do fornecedor sugerido, para considerar o prazo real antes de fechar.
2. Como comprador chefe, quero ser avisado quando o corpus registra encalhe de um produto parecido, para não repetir o erro do Veraneio.
3. Como comprador chefe, quero ser avisado quando o corpus registra venda forte do produto numa época do ano, para lembrar da sazonalidade que não está no ERP.
4. Como comprador chefe, quero que cada sinal diga de qual trecho veio, para conferir.
5. Como comprador chefe, quero que os sinais nunca mudem a quantidade calculada, para a sugestão continuar seguindo a política que eu defini.
6. Como comprador chefe, quero ver marcada no texto toda citação que o Copilot não conseguiu confirmar, para não confiar numa fonte que não diz aquilo.

### Desenvolvedor

7. Como desenvolvedor, quero os limiares dos sinais e da citação medidos contra o Jev real em casos rotulados, para não usar um valor de receita como se fosse do nosso domínio.
8. Como desenvolvedor, quero calcular os sinais uma vez por par (fornecedor, produto), e não por SKU, para uma pergunta sobre um produto com 12 SKUs não custar 12 buscas.
9. Como desenvolvedor, quero a extração e a marcação de citações em funções puras, para testar os casos de borda sem rede.

## Implementation Decisions

### Sinais do corpus

**Port**: `DecisionModel.avaliar_sinais(fornecedor: str, produto: ProdutoDoSinal, trechos: Sequence[Trecho]) -> list[AvaliacaoSinais]`. Um request por trecho, até 8 em paralelo (como `avaliar_trechos`), com o state `{"fornecedor": <nome>, "produto": {"nome", "categoria"}, "trecho": {"titulo", "tipo", "data", "texto"}}` e três `Noul`:

| Campo | Instructions | Criteria true | Criteria false |
|---|---|---|---|
| `atraso_do_fornecedor` | O `trecho` relata que o fornecedor `fornecedor` atrasou entregas ou entregou depois do prazo combinado? | O trecho conta atraso, entrega fora do prazo ou lead time real maior que o contratado desse mesmo fornecedor. | O trecho não fala de entrega desse fornecedor, fala de outro fornecedor ou diz que ele cumpre os prazos. |
| `demanda_sazonal` | O `trecho` relata que o `produto` ou a categoria dele vende mais numa data comemorativa ou época do ano? | O trecho cita venda maior desse produto ou da categoria dele no Natal, no Dia das Mães, no inverno, no verão ou em outra época. | O trecho não fala de venda por época desse produto nem da categoria dele. |
| `encalhe` | O `trecho` relata que o `produto` ou a categoria dele encalhou ou sobrou em estoque depois de uma compra? | O trecho conta que uma compra desse produto ou da categoria dele vendeu abaixo do esperado, ficou parada ou precisou de liquidação. | O trecho não fala de sobra de estoque desse produto nem da categoria dele. |

`ProdutoDoSinal`: `nome`, `categoria`. `AvaliacaoSinais`: `trecho_id`, as três probabilidades e `modelo`. `InMemoryDecisionModel` ganha a configuração por trecho, padrão e modo de falha, como nos outros métodos.

**Serviço** `SinaisCorpus` (`src/ai/sinais.py`):

- `para_sugestao(sugestao: SugestaoPedido, sku: SKU) -> list[SinalCorpus]`. Sugestão sem fornecedor (quantidade zero por SKU novo, sem giro ou sem fornecedor) não tem sinal. Caso contrário:
  1. Busca focada: `BuscaContexto.buscar(consulta, k=K_SINAIS, com_conflitos=False)` com `consulta = f"{fornecedor} e {produto}: atrasos de entrega, vendas por época do ano e estoque encalhado"` e `K_SINAIS = 15`. `buscar` ganha o parâmetro `com_conflitos` (padrão `True`, o comportamento do M4 não muda).
  2. Os trechos `aceito` e `conflitante` da busca, até `MAX_TRECHOS_SINAIS = 10` por similaridade, vão para `avaliar_sinais`.
  3. Um sinal por tipo cuja probabilidade passa de `LIMIARES_SINAIS.<tipo>` em pelo menos um trecho, com os ids desses trechos (por probabilidade, maior primeiro) e a maior probabilidade.
- Cache por chamada: `para_sugestoes(pares: Sequence[tuple[SugestaoPedido, SKU]]) -> dict[str, list[SinalCorpus]]` (chave `sku_code`) calcula uma vez por par (fornecedor, produto) e reaproveita para os SKUs do mesmo par.
- `SinalCorpus`: `tipo: Literal["atraso_do_fornecedor", "demanda_sazonal", "encalhe"]`, `mensagem` (feita em código), `trechos: list[str]`, `probabilidade`.
- Mensagens: "Os documentos relatam atraso de entrega da <fornecedor>.", "Os documentos relatam venda forte de <produto> em alguma época do ano.", "Os documentos relatam encalhe de <produto> ou da categoria dele numa compra anterior."
- `SugestaoComSinais` (`sugestao`, `sinais`) em `src/ai/schemas.py`. O `purchasing` não muda e não conhece o corpus.

**Avaliação** (mesmo processo do ticket 01 do M5): `evals/sinais.json` com pelo menos 15 casos `(fornecedor, produto, trecho_id, esperado: {atraso_do_fornecedor, demanda_sazonal, encalhe})`, rotulados antes de rodar a partir do corpus, com pelo menos 3 positivos de cada tipo e casos de fornecedor ou produto trocado (ex: trecho de atraso da Katrina perguntado para a Malha Fina). `scripts/avaliar_sinais.py` roda contra o Jev real, grava as respostas cruas em `evals/resultados/sinais-<data>.json`, aceita `--de-arquivo` e varre o limiar de cada tipo de 0,30 a 0,90. **Regra**: por tipo, o limiar com mais acertos; empate, o mais alto. Não é gate.

### Verificação de citações

**Funções puras** (`src/ai/citacoes.py`):

- `extrair_citacoes(texto) -> list[Citacao]`: cada `[<id>]` cujo conteúdo tem o formato de id de trecho (`<caminho>.md#<slug>`), com a `afirmacao` = a frase que contém a citação, sem os colchetes. Frase termina em `.`, `!`, `?` seguido de espaço ou em quebra de linha; item de lista é uma frase. Colchetes com mais de um id separados por `;` ou `,` viram uma citação por id.
- `marcar_citacoes(texto, verificacoes) -> str`: troca cada citação não confirmada pela marcação do veredito, mantendo o id: `[<id> - não confirmada]` (`sem_suporte` e `incerta`), `[<id> - o trecho diz o contrário]` (`contradita`), `[<id> - fonte inexistente]` (`inventada`). Citação `confirmada` fica como está.

**Port**: `DecisionModel.verificar_citacoes(pares: Sequence[tuple[str, Trecho]]) -> list[AvaliacaoCitacao]`, um request por par (afirmação, trecho), até 8 em paralelo, state `{"afirmacao": ..., "trecho": {"titulo", "tipo", "data", "texto"}}` e uma `Choice`:

- instructions: "Como o `trecho` se relaciona com a `afirmacao`?"
- `sustenta`: "O trecho afirma o que a afirmação diz, ou deixa claro que é verdade."
- `contradiz`: "O trecho afirma o contrário da afirmação, ou deixa claro que ela é falsa."
- `nao_trata`: "O trecho não fala do que a afirmação diz, nem a favor nem contra."

`AvaliacaoCitacao`: `afirmacao`, `trecho_id`, `escolha`, `confianca`, `probabilidades`, `modelo`.

**Veredito** (código, `VerificacaoCitacao` com `trecho_id`, `afirmacao`, `veredito`, `confianca: float | None`): id fora do contexto -> `inventada` (sem Jev); confiança abaixo de `LIMIAR_CITACAO` -> `incerta`; senão `sustenta` -> `confirmada`, `contradiz` -> `contradita`, `nao_trata` -> `sem_suporte`. `LIMIAR_CITACAO` parte de 0,80 (receita do TypeSafe) e é ajustado pela avaliação.

**Avaliação**: `evals/citacoes.json` com pelo menos 15 pares `(afirmacao, trecho_id, esperado)` escritos à mão a partir do corpus, pelo menos 5 de cada relação, incluindo afirmações com número trocado (ex: "a Katrina entrega em 30 dias" contra a cláusula de 45 dias) e afirmações verdadeiras sobre outro fornecedor. `scripts/avaliar_citacoes.py` roda contra o Jev real, grava as respostas cruas em `evals/resultados/citacoes-<data>.json`, aceita `--de-arquivo` e reporta acerto por relação e, para limiares de 0,50 a 0,95, quantas citações ficariam `incerta` e quantos erros sobrariam entre as decididas. **Regra**: o menor limiar sem nenhuma `confirmada` errada (citação que não sustenta marcada como confirmada é o erro que importa); se nenhum zerar, 0,95 e o risco fica registrado.

### Chat

No `Copilot` do M5:

- `sugestao_compra` com SKUs identificados: depois das sugestões, `SinaisCorpus.para_sugestoes` para as sugestões com fornecedor. A montagem passa a ter `sugestoes: list[SugestaoComSinais]`, e o contexto renderiza os sinais logo abaixo de cada sugestão, com os ids dos trechos de origem. Os trechos que deram origem a sinais entram na seção de trechos do contexto (sem passar de `MAX_TRECHOS_NO_CONTEXTO` somados aos da busca da pergunta; os da pergunta têm prioridade), para o redator poder citá-los.
- Toda resposta redigida por um LLM (redator diferente de `sem_llm`) passa pela verificação: `extrair_citacoes`, vereditos, `marcar_citacoes`. A `RespostaCopilot` ganha `citacoes: list[VerificacaoCitacao]` e a resposta final é o texto marcado. Resposta do `RedatorSemLLM`, esclarecimento e fora de escopo não passam pela verificação.
- `DecisaoIndisponivel` durante sinais ou verificação: a resposta sai sem sinais ou sem verificação, com uma observação ("não consegui calcular os sinais do corpus" ou "não consegui verificar as citações"). Não derruba o chat, porque o entendimento já aconteceu e os dois são aumento de valor. As citações não verificadas ficam marcadas como `incerta`.
- Migration `0005`: `copilot.registros_decisao` ganha `sinais jsonb not null default '[]'` e `citacoes jsonb not null default '[]'`, gravados pelo `Copilot`.

### Endpoint

`GET /skus/{sku_code}/sugestao-compra/sinais` em `src/api/skus.py`: 404 para SKU inexistente, 503 sem Jev, lista vazia quando a sugestão não tem fornecedor. Devolve `list[SinalCorpus]` em DTO HTTP.

## Testing Decisions

- **`SinaisCorpus`**: com `InMemoryDecisionModel`, embedder falso e repositório em memória. Sinal só acima do limiar; ids ordenados por probabilidade; sugestão sem fornecedor não busca; um cálculo por par (fornecedor, produto) em `para_sugestoes`; `com_conflitos=False` não chama `avaliar_conflitos`.
- **`JevDecisionModel.avaliar_sinais` e `verificar_citacoes`**: com cliente TypeSafe falso (state, perguntas, mapeamento, erro vira `DecisaoIndisponivel`) e um `externo` cada.
- **`citacoes`**: frase com uma e com duas citações; citação no meio e no fim da frase; item de lista; colchete que não é id de trecho fica fora; `;` e `,` com vários ids; marcação de cada veredito; texto sem citação volta igual.
- **`Copilot`**: sinais no contexto e na resposta de `sugestao_compra`; verificação só para redator LLM; `inventada` sem chamar o Jev; queda do Jev nos sinais e na verificação vira observação.
- **Registro**: sinais e citações gravados e lidos (contrato in-memory e Postgres).
- **HTTP**: `/skus/{sku_code}/sugestao-compra/sinais` feliz, 404, 503, sem fornecedor.
- **Smoke** (`externo`): sinais de um SKU da Katrina trazem `atraso_do_fornecedor`.

## Out of Scope

- Sinais que alteram a quantidade ou o fornecedor da sugestão (nunca, pela ADR-0003).
- Cache de sinais entre requisições ou calculados na ingestão.
- Verificar citação de trecho pelo texto citado entre aspas (o redator cita por id).
- Reescrever a resposta quando uma citação falha: o texto só é marcado.
- Priorização da fila pelos sinais (M7, que reaproveita `SinaisCorpus`).

## Further Notes

- Custo de uma pergunta de sugestão com sinais: a busca da pergunta (até 75 requests), uma busca focada por par (até 30 requests) e até 10 requests de sinais por par, mais uma verificação por citação. Na casa de US$ 0,005.
- Latência: a busca focada e os sinais somam uns 3 s por par. Com um par por pergunta, a sugestão fica entre 6 e 9 s.
- Ordem dos tickets: 01 (sinais) e 02 (verificação) mexem nos mesmos arquivos do `ai` e rodam em sequência. 03 integra no chat e fecha o milestone.
