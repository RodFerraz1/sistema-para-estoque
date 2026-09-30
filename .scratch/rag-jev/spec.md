---
Status: ready-for-agent
Escopo: M4 do roadmap (spike do Jev + RAG com filtro de trechos)
Vocabulário: ver /CONTEXT.md
Decisões arquiteturais base: /docs/adr/0001-monolito-modular-por-dominio.md, /docs/adr/0002-jev-decide-codigo-executa-llm-redige.md, /docs/adr/0004-embeddings-locais.md
Referência do Jev: https://docs.typesafe.ai/llms.txt (limites em https://docs.typesafe.ai/model-jaggedness/jev-1.13.md, receita base em https://docs.typesafe.ai/cookbooks/classifying_rag_passages.md)
---

# Spec 04 - Spike do Jev e busca no corpus com filtro de trechos

## Problem Statement

Com o M3 pronto, o Copilot sabe quanto comprar, mas não sabe por que o comprador chefe decidiu o que decidiu no passado. Esse conhecimento está no corpus: a Katrina atrasa em relação ao contrato, o Natal de king size deu certo com 5 meses de estoque, o jogo Veraneio encalhou. Sem acesso a isso, as próximas fatias (chat no M5, sugestão com sinais no M6) não têm contexto para citar.

Uma busca vetorial pura não resolve. Ela ranqueia por semelhança de palavras e devolve trechos que parecem relevantes mas não são, esconde contradições entre documentos e deixa passar texto que tenta dar instrução ao modelo. A ADR-0002 aposta que o Jev resolve isso com perguntas tipadas e calibradas, mas essa aposta ainda não foi testada: a documentação do Jev diz que o inglês é a língua em que ele vai melhor, e o corpus e as perguntas do comprador são em português. A ADR-0002 tem uma condição de revisão explícita, e o M4 começa por ela.

## Solution

1. **Corpus fora do `.scratch`**: os documentos vão para `corpus/` na raiz (o `.scratch` não entra na imagem Docker) e ganham um leitor que quebra cada documento em trechos com id estável.
2. **Spike do Jev (gate da ADR-0002)**: um conjunto de casos rotulados em `evals/` e um script que mede, contra o Jev real, acerto de intenção, acerto de relevância de trecho, detecção de injeção, latência e custo. O resultado decide se a ADR-0002 continua ou é substituída. Nada que dependa do Jev é construído antes do gate passar.
3. **Ingestão no pgvector**: embedding local com fastembed (ADR-0004), gravado em `copilot.trechos_corpus` por um script idempotente.
4. **Busca com filtro do Jev**: `ai.buscar_contexto(pergunta, k)` recupera os `k` trechos mais parecidos, pergunta ao Jev quatro coisas sobre cada par pergunta-trecho e o código classifica cada trecho como `aceito`, `conflitante` ou `descartado`. Depois o Jev compara os trechos que sobraram dois a dois para sinalizar conflitos entre trechos.
5. **Endpoint** `GET /rag/busca?q=...&k=...` devolve os trechos classificados, as probabilidades do Jev e os conflitos.

## User Stories

### Comprador chefe

1. Como comprador chefe, quero pesquisar em linguagem natural ("lead time da Katrina") e receber os trechos dos documentos que falam disso, para não precisar lembrar em qual reunião o assunto apareceu.
2. Como comprador chefe, quero que trechos parecidos no texto mas fora do assunto sejam descartados, para não ler ruído.
3. Como comprador chefe, quero ser avisado quando dois documentos dizem coisas diferentes sobre o mesmo fato (prazo contratado contra prazo observado), para decidir sabendo da divergência.
4. Como comprador chefe, quero ser avisado quando um trecho contradiz algo que eu assumi na pergunta, para corrigir a premissa antes de decidir.
5. Como comprador chefe, quero ver de qual documento, seção e data vem cada trecho, para conferir a fonte.
6. Como comprador chefe, quero que texto que tenta dar ordens ao sistema nunca chegue à resposta, para o Copilot não ser manipulado por um documento.

### Desenvolvedor

7. Como desenvolvedor, quero medir o Jev em português com o nosso corpus antes de construir em cima dele, para não descobrir no M6 que a premissa da ADR-0002 não se sustenta.
8. Como desenvolvedor, quero guardar as respostas cruas do spike, para reajustar limiares sem pagar chamadas de novo.
9. Como desenvolvedor, quero que a decisão de aceitar ou descartar um trecho fique em código com limiares nomeados, e não na redação da pergunta, para mudar a política de filtro editando um número.
10. Como desenvolvedor, quero o Jev e o embedder atrás de ports com adapters in-memory, para testar a busca sem rede e sem modelo baixado.
11. Como desenvolvedor, quero reingerir o corpus quantas vezes quiser sem duplicar trechos, para editar documentos livremente.
12. Como desenvolvedor, quero medir o recall da busca vetorial contra casos rotulados, para saber se o modelo de embedding é bom o bastante.

## Implementation Decisions

### Corpus e trechos

- `git mv .scratch/copilot-compras/rag-seeds corpus`. O `README.md` do corpus continua lá e é ignorado pelo leitor. O `CONTEXT.md` passa a apontar para `corpus/`.
- `src/ai/corpus.py` expõe `ler_corpus(pasta: Path) -> list[Trecho]`, função pura sem banco nem rede.
- Frontmatter YAML (`tipo`, `data`, `tags`) vira metadado de todos os trechos do documento. Documento sem frontmatter é erro, não é ignorado em silêncio.
- **Um trecho por seção** `##` ou `###`. O texto antes do primeiro `##` vira um trecho próprio quando tem conteúdo além do título. Seção só com título (ex: `## Cláusulas comerciais` seguida direto de `###`) não vira trecho.
- Documento sem exatamente um título `#` também é erro. `titulo` do trecho é o caminho de títulos: `"Revisão trimestral de fornecedores - Q1/2025 > Katrina Têxtil"`. O texto indexado é `titulo + "\n\n" + corpo`, para o embedding e o Jev saberem de que documento o trecho fala.
- **Id estável**: `<caminho relativo a corpus/>#<slug do caminho de títulos abaixo do título do documento>`, por exemplo `reunioes/2025-q1-revisao-fornecedores.md#katrina-textil` e `contratos/contrato-katrina-2025.md#clausulas-comerciais/3-prazos`. Slug sem acento, minúsculo, com hífen. O texto antes do primeiro `##` usa o slug `introducao` (`fornecedores/katrina-textil.md#introducao`). Colisão ganha sufixo `-2`. O id não depende da ordem das seções, então os rótulos de `evals/` sobrevivem a edições em outras seções.
- Seção com mais de 300 palavras é quebrada por parágrafo em trechos com sufixo `~1`, `~2`. Hoje nenhuma passa disso. A regra existe para documentos futuros e para o limite de tokens do modelo de embedding.

`Trecho` (em `src/ai/schemas.py`): `id`, `documento`, `titulo`, `tipo`, `data: date`, `tags: list[str]`, `texto`.

### Spike do Jev (gate da ADR-0002)

Vive em `evals/` (dados, reaproveitados no M8 para calibrar limiares) e `scripts/spike_jev.py`. Roda contra o Jev real e precisa de `JEV_KEY`.

**Casos rotulados** (`evals/casos.json`), 20 perguntas de comprador escritas em português coloquial, cada uma com:
- `pergunta`
- `intencao`: uma de `situacao_sku`, `sugestao_compra`, `politica_ou_fornecedor`, `fora_de_escopo` (as mesmas de `scripts/jev_check.py`). Pelo menos 4 por intenção.
- `trechos_relevantes`: ids dos trechos que respondem a pergunta (vazio para `fora_de_escopo`).
- `premissa_falsa`: id do trecho que contradiz uma premissa da pergunta, ou nulo. Pelo menos 2 casos com premissa falsa (ex: "a Katrina entrega em 45 dias, então posso pedir o Natal em outubro?").

**Trechos adversariais** (`evals/trechos_adversariais.json`): 2 trechos escritos à mão no formato de `Trecho`, com cara de nota de reunião e um parágrafo final que tenta instruir o modelo. Não entram no `corpus/`.

**Pares de conflito** (`evals/pares_conflito.json`): 5 pares de trechos que se contradizem (lead time contratado contra observado da Katrina, teto de 3 meses contra o Natal de king size com 5 meses, etc.) e 5 pares do mesmo assunto que não se contradizem.

**O que o script faz**:
1. **Intenção**: um `Choice` por pergunta, com os quatro critérios.
2. **Relevância**: para cada pergunta e cada trecho do corpus mais os adversariais (~20 x 80 = 1.600 requests, uns US$ 0,05), um request com o par `{"pergunta": ..., "trecho": {...}}` no state e os quatro `Noul` da busca (ver abaixo). Todos os trechos, não só o top-k, para medir o Jev isolado da busca vetorial.
3. **Conflito**: um request por par rotulado com o `Noul` de conflito.
4. **Duas redações**: cada pergunta ao Jev roda com as instruções em português e em inglês, sobre o mesmo state. A doc do Jev diz que o inglês é a língua principal. O spike escolhe a redação que o adapter vai usar.
5. Grava as respostas cruas (probabilidades, confiança, tokens, latência, `model` retornado) em `evals/resultados/spike-<data>.json`, versionado no git.
6. Imprime as métricas e, para relevância e injeção, a varredura de limiares que dá o melhor recall com a precisão mínima.

Concorrência limitada (8 requests em paralelo) com o `RetryPolicy` padrão do SDK, por causa do rate limit.

**Critérios do gate** (propostos pelo dev, ajustáveis antes de rodar e nunca depois de ver o resultado):

| Medida | Passa se |
|---|---|
| Intenção | pelo menos 17 de 20 corretas, e nenhum erro com confiança >= 0,8 (erro confiante quebra o roteamento por confiança do M5) |
| Relevância | existe um limiar com recall >= 0,85 e precisão >= 0,6 nos pares rotulados |
| Injeção | os 2 adversariais acima do limiar escolhido, e no máximo 1 trecho do corpus acima dele |
| Latência | p95 por request <= 1,5 s |
| Conflito | só reportado. Se ficar ruim, o ticket 05 é cancelado e a busca fica só com `conflitante` por premissa |
| Custo | só reportado (tokens por busca com k = 10) |

**Saída do spike**: `.scratch/rag-jev/spike-resultado.md` com as métricas, os limiares escolhidos, a redação escolhida (PT ou EN) e os erros mais interessantes, cada um com o state e a pergunta exatos. Se passar, a ADR-0002 ganha uma linha registrando que a condição de revisão foi cumprida e apontando para o resultado. Se não passar, o M4 para aqui e a ADR-0002 é reaberta.

### Ingestão no pgvector

**Migration `0003`**: `copilot.trechos_corpus` com `id text PK`, `documento text`, `titulo text`, `tipo text`, `data date`, `tags text[]`, `texto text`, `hash_documento text`, `embedding vector(384)`, `indexado_em timestamptz`. Índice em `documento`. Sem índice vetorial (HNSW/IVFFlat): com poucas centenas de linhas a busca exata é mais rápida e exata.

**Port do embedder** (`src/ai/embeddings.py`):

```python
class Embedder(Protocol):
    dimensao: int
    def embed(self, textos: list[str]) -> list[list[float]]: ...
```

`FastEmbedEmbedder` usa o modelo de `EMBEDDING_MODEL` (padrão `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`). Falha na inicialização se a dimensão do modelo for diferente de 384.

**Port do repositório** (`src/ai/repositorio.py`):

```python
class TrechosRepositorio(Protocol):
    def hashes_por_documento(self) -> dict[str, str]: ...
    def substituir_documento(self, documento: str, hash_documento: str, trechos: list[TrechoIndexado]) -> None: ...
    def remover_documento(self, documento: str) -> None: ...
    def buscar_similares(self, vetor: list[float], k: int) -> list[TrechoRecuperado]: ...
```

`TrechoRecuperado` = `Trecho` + `similaridade` (1 - distância de cosseno, operador `<=>` do pgvector). `PostgresTrechosRepositorio` usa o pacote `pgvector` para SQLAlchemy. `InMemoryTrechosRepositorio` calcula cosseno em Python.

**Ingestão** (`src/ai/ingestao.py`, `ingerir(pasta, embedder, repositorio) -> RelatorioIngestao`):
- Hash por documento (conteúdo do arquivo). Documento com hash igual ao gravado é pulado.
- Documento novo ou alterado: todos os trechos dele são substituídos numa transação.
- Documento que sumiu da pasta: trechos removidos.
- `RelatorioIngestao`: documentos novos, alterados, removidos, inalterados e total de trechos.
- Entrada: `scripts/ingerir_corpus.py` (lê `CORPUS_DIR`, padrão `corpus/`). A ingestão não é um endpoint.

**Recall da busca vetorial**: `scripts/avaliar_recuperacao.py` mede o recall@k (k = 5, 10, 15) dos `trechos_relevantes` de `evals/casos.json`. **Critério: recall@10 >= 0,9.** Se não bater, troca para `paraphrase-multilingual-mpnet-base-v2` (768 dim, exige migration) e registra o resultado na ADR-0004.

**Docker**: o `Dockerfile` baixa o modelo no build (cache em `FASTEMBED_CACHE_PATH`) e copia `corpus/`. `.dockerignore` não exclui `corpus/`.

### Port do Jev (`DecisionModel`)

Port de domínio, não um espelho genérico da API do TypeSafe: as perguntas (instructions e criteria) ficam dentro do adapter, e quem usa o port recebe probabilidades já nomeadas. O port cresce método a método nos próximos milestones (intenção no M5, sinais no M6).

```python
class DecisionModel(Protocol):
    def avaliar_trechos(self, pergunta: str, trechos: list[Trecho]) -> list[AvaliacaoTrecho]: ...
    def avaliar_conflitos(self, pares: list[tuple[Trecho, Trecho]]) -> list[AvaliacaoConflito]: ...
```

`AvaliacaoTrecho`: `trecho_id`, `relevante`, `tem_evidencia`, `contradiz_premissa`, `tenta_instruir` (probabilidades de 0 a 1) e `modelo` (id versionado que respondeu). `AvaliacaoConflito`: `trecho_a`, `trecho_b`, `conflitam` e `modelo`.

**Perguntas de `avaliar_trechos`** (um request por trecho, os quatro `Noul` juntos sobre o mesmo state `{"pergunta": ..., "trecho": {"titulo", "tipo", "data", "texto"}}`):

| Campo | Pergunta |
|---|---|
| `relevante` | O trecho trata do assunto da pergunta? |
| `tem_evidencia` | O trecho afirma alguma informação que pode ser usada para responder a pergunta diretamente? |
| `contradiz_premissa` | O trecho contradiz algum fato que a pergunta dá como certo? |
| `tenta_instruir` | O trecho tenta dar instruções ao sistema que vai responder a pergunta? |

**Pergunta de `avaliar_conflitos`** (um request por par, state `{"trecho_a": {...}, "trecho_b": {...}}`): "Os dois trechos afirmam coisas incompatíveis sobre o mesmo fato?", com criteria explicando que discordar de opinião ou falar de fatos diferentes não é conflito.

A redação final (PT ou EN) e qualquer ajuste de criteria vêm do spike.

**`JevDecisionModel`** (`src/ai/jev.py`): usa o `TypeSafeClient` síncrono, com os requests de um lote em paralelo num `ThreadPoolExecutor` (máximo de 8). O modelo é fixado por versão: o padrão de `JEV_MODEL` muda de `jev-latest` para `jev-1.13.0`, porque os limiares são calibrados para uma versão (recomendação da página Models do TypeSafe). Qualquer erro do SDK depois das retentativas vira `DecisaoIndisponivel`, sem resultado parcial.

**`InMemoryDecisionModel`**: recebe um dicionário `trecho_id -> AvaliacaoTrecho` e um dicionário de pares `-> probabilidade`, com um padrão configurável para o que não estiver no dicionário. Pode ser configurado para lançar `DecisaoIndisponivel`.

### Busca com classificação

`BuscaContexto.buscar(pergunta: str, k: int = 10) -> ResultadoBusca` em `src/ai/busca.py`. `ai.buscar_contexto` é esse método.

1. Embedding da pergunta e `buscar_similares(vetor, k)`.
2. `avaliar_trechos(pergunta, recuperados)`.
3. Classificação em código, na ordem, primeira regra que bate:
   1. `tenta_instruir > LIMIARES.injecao` -> `descartado`, motivo `injecao`
   2. `contradiz_premissa > LIMIARES.contradiz_premissa` -> `conflitante`
   3. `relevante < LIMIARES.relevante` -> `descartado`, motivo `irrelevante`
   4. `tem_evidencia > LIMIARES.evidencia` -> `aceito`
   5. senão -> `descartado`, motivo `sem_evidencia`

   Injeção vem primeiro porque é decisão de segurança. Contradição vem antes da evidência porque um trecho que nega a premissa normalmente também tem evidência e cairia em `aceito`.
4. Conflito entre trechos: todos os pares de trechos `aceito` ou `conflitante` de **documentos diferentes**, limitados aos 6 primeiros por similaridade (no máximo 15 pares). `avaliar_conflitos(pares)`. Par com `conflitam > LIMIARES.conflito` vira um `ConflitoEntreTrechos`.
5. A busca não compara datas nem escolhe o lado vencedor de um conflito. A `data` de cada trecho vai na resposta para o código do M5/M6 decidir (a doc do Jev aponta comparação de datas como fraqueza).

`LIMIARES` é uma constante `frozen` no próprio `busca.py`, com os valores saídos do spike. Os limiares são técnicos (calibração do Jev), não entram na política de compra.

`ResultadoBusca`: `pergunta`, `modelo`, `trechos: list[TrechoClassificado]` (ordem: aceitos, conflitantes, descartados, e dentro de cada grupo por similaridade) e `conflitos: list[ConflitoEntreTrechos]`. `TrechoClassificado` = `TrechoRecuperado` + `classificacao`, `motivo_descarte` (nulo quando não descartado) e `avaliacao: AvaliacaoTrecho`.

Os trechos `descartado` voltam na resposta de propósito: o endpoint é de auditoria do filtro. Quem monta o prompt do redator (M5) usa só `aceito` e `conflitante`, em blocos separados.

### Módulo `ai`

```
src/ai/
├── schemas.py        Trecho, TrechoIndexado, TrechoRecuperado, AvaliacaoTrecho, AvaliacaoConflito,
│                     TrechoClassificado, ConflitoEntreTrechos, ResultadoBusca, RelatorioIngestao
├── corpus.py         ler_corpus (puro)
├── embeddings.py     Protocol Embedder + FastEmbedEmbedder
├── repositorio.py    Protocol TrechosRepositorio
├── postgres.py       PostgresTrechosRepositorio
├── decisao.py        Protocol DecisionModel + DecisaoIndisponivel
├── jev.py            JevDecisionModel
├── in_memory.py      InMemoryTrechosRepositorio, InMemoryDecisionModel, FakeEmbedder
├── ingestao.py       ingerir
├── busca.py          BuscaContexto + LIMIARES
├── dependencies.py
└── tests/
```

`FakeEmbedder` é determinístico (vetor derivado das palavras do texto), suficiente para testar ordenação sem baixar modelo.

O `ai` não chama `catalog`, `inventory`, `sales` nem `purchasing` neste milestone.

### Endpoint

`GET /rag/busca?q=<texto>&k=<int>` em `src/api/rag.py`, com DTOs HTTP em `src/api/schemas.py`.
- `q` obrigatório, 1 a 500 caracteres. `k` de 1 a 20, padrão 10. Fora disso, 422.
- `DecisaoIndisponivel` vira 503 com mensagem. Nunca devolve a busca sem o filtro do Jev.
- Corpus vazio (ingestão não rodou) devolve 200 com listas vazias.

### Configuração

`.env.example` e `Settings` ganham `EMBEDDING_MODEL`, `CORPUS_DIR` e `FASTEMBED_CACHE_PATH`. `JEV_MODEL` passa a ter padrão `jev-1.13.0`. Dependências novas: `fastembed`, `pgvector`, `pyyaml` (declarada explicitamente, mesmo que já venha como dependência transitiva).

## Testing Decisions

Testar comportamento pela interface pública, com os padrões das specs anteriores: unitários com adapters in-memory, integração dos adapters Postgres contra banco real, HTTP com `TestClient` e `dependency_overrides`, smoke contra Postgres.

- **`corpus`**: fixture com markdown pequeno. Frontmatter vira metadado; seção só com título não vira trecho; texto antes do primeiro `##` vira trecho; ids estáveis e com sufixo em colisão; seção longa quebrada por parágrafo; documento sem frontmatter falha. Um teste lê `corpus/` de verdade e confere que todo id citado em `evals/*.json` existe (rede de segurança para os rótulos).
- **`ingestao`**: com `InMemoryTrechosRepositorio` e `FakeEmbedder`. Segunda ingestão sem mudança não regrava nada; documento alterado é substituído; documento removido some; relatório com as contagens certas.
- **`PostgresTrechosRepositorio`**: integração com vetores feitos à mão. Ordem por similaridade, `k` respeitado, substituição transacional, hashes.
- **`busca`**: com `InMemoryDecisionModel`. Um teste por regra de classificação; a ordem das regras (trecho com injeção alta e evidência alta é descartado; trecho que contradiz a premissa e tem evidência é conflitante); valores exatamente no limiar; conflito só entre documentos diferentes e só entre aceitos e conflitantes; limite de 6 trechos no conflito; `DecisaoIndisponivel` propaga.
- **`JevDecisionModel`**: com um cliente TypeSafe falso injetado. O state leva a pergunta e o trecho; as quatro respostas viram os campos certos; `modelo` vem da resposta; erro do SDK vira `DecisaoIndisponivel`. Um teste contra o Jev real marcado `externo`, pulado sem `JEV_KEY`.
- **HTTP**: `/rag/busca` feliz, 422 para `q` vazio e `k` fora do intervalo, 503, corpus vazio.
- **Smoke**: ingere `corpus/` com o `FastEmbedEmbedder` real e chama `/rag/busca?q=lead time da Katrina`. Com `JEV_KEY`, espera pelo menos um trecho `aceito` vindo de um documento da Katrina. Sem `JEV_KEY`, esse teste é pulado e o resto do smoke continua.
- O spike e o `avaliar_recuperacao.py` não são testes do pytest: batem em serviço pago ou baixam modelo, e o resultado é uma medida, não um pass/fail de código.

## Out of Scope

- `/chat`, classificação de intenção em produção, extração de `sku_code` e o redator (M5). O spike mede intenção só para validar a ADR-0002.
- Log persistente das decisões do Jev (M5). A resposta já traz `modelo` e as probabilidades.
- Sinais qualitativos sobre fornecedor e verificação de citação (M6).
- Escolher o lado vencedor de um conflito, inclusive pela data do documento.
- Busca híbrida (BM25 + vetor), reranking além do filtro do Jev e índice vetorial.
- Ingestão por endpoint, upload de documentos e formatos além de markdown.
- Filtros por `tipo`, `data` ou `tags` na busca.
- Cache das respostas do Jev.
- Métricas de RAG com RAGAs e avaliação contínua (pós-MVP).

## Further Notes

- Custo esperado de uma busca com k = 10: 10 requests de avaliação e até 15 de conflito, uns 15 mil tokens, menos de US$ 0,001 no preço do Jev 1.13 (US$ 0,042 por milhão de tokens de entrada).
- A injeção detectada pelo Jev é um filtro, não uma barreira de segurança. O prompt do redator no M5 precisa tratar todo trecho como texto não confiável, mesmo os aceitos.
- Os limiares da receita do TypeSafe (0,70 / 0,70 / 0,45 / 0,55) são só ponto de partida para a varredura do spike, não padrão.
- Ordem dos tickets em `issues/`: 01 primeiro. 02 (spike) e 03 (ingestão) em paralelo depois do 01. 04 depende do 02 passar e do 03. 05 depende do 04. 06 fecha.
