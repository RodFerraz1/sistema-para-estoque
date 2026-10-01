# 03: Ingestão do corpus no pgvector

**Status:** done
**Blocked by:** 01 (Corpus em `corpus/` e leitura em trechos)
**Spec:** `.scratch/rag-jev/spec.md`
**ADR:** `docs/adr/0004-embeddings-locais.md`

## What to build

Os trechos do corpus viram vetores com um embedding local (fastembed) e ficam gravados em `copilot.trechos_corpus`. Um script idempotente reingere só o que mudou. A busca por similaridade existe no repositório, mas ainda não tem endpoint. Não depende do Jev, então roda em paralelo com o spike.

## Acceptance criteria

- [x] Migration `0003` cria `copilot.trechos_corpus` com as colunas da spec, `embedding vector(384)` e índice em `documento`. `downgrade` remove a tabela.
- [x] Port `Embedder` e `FastEmbedEmbedder` (modelo de `EMBEDDING_MODEL`, cache em `FASTEMBED_CACHE_PATH`), que falha na inicialização se a dimensão não for 384. `FakeEmbedder` determinístico em `in_memory.py`.
- [x] Port `TrechosRepositorio` (`hashes_por_documento`, `substituir_documento`, `remover_documento`, `buscar_similares`), com `PostgresTrechosRepositorio` (pacote `pgvector`, operador `<=>`) e `InMemoryTrechosRepositorio`.
- [x] `ingerir(pasta, embedder, repositorio) -> RelatorioIngestao`: pula documento com hash igual, substitui documento alterado numa transação, remove documento que sumiu.
- [x] `scripts/ingerir_corpus.py` lê `CORPUS_DIR` e imprime o relatório.
- [x] `scripts/avaliar_recuperacao.py` imprime o recall@5, @10 e @15 dos `trechos_relevantes` de `evals/casos.json` (se o 02 ainda não tiver criado o arquivo, o script falha com mensagem clara). Se recall@10 < 0,9, abre a conversa com o dev sobre trocar o modelo (ADR-0004) antes de fechar o ticket.
- [x] `Settings` e `.env.example` com `EMBEDDING_MODEL`, `CORPUS_DIR` e `FASTEMBED_CACHE_PATH`. Dependências `fastembed` e `pgvector` no `pyproject.toml`.
- [x] `Dockerfile` baixa o modelo no build e a imagem contém `corpus/`.
- [x] Testes: ingestão com in-memory (idempotência, alteração, remoção, contagens); integração do repositório Postgres com vetores feitos à mão (ordem por similaridade, `k`, substituição, hashes).
- [x] `uv run pytest` verde.

## Comments

**2026-09-29 (agente):** ingestão pronta e testada (contrato do repositório roda contra in-memory e Postgres). `scripts/avaliar_recuperacao.py` rodou contra `evals/casos.json` e **o critério não passou**, então o ticket fica aberto até o dev decidir o modelo (ADR-0004).

| Modelo | dim | recall@5 | recall@10 | recall@15 |
|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` (atual) | 384 | 0,319 | **0,532** | 0,638 |
| `paraphrase-multilingual-mpnet-base-v2` (troca prevista na spec) | 768 | 0,319 | **0,574** | 0,660 |

Recall contado sobre os 47 trechos rotulados de 12 perguntas (micro). Por pergunta (macro), o MiniLM dá 0,581 no @10. O `multilingual-e5-large` não carrega no onnxruntime atual (erro de caminho dos dados externos do ONNX) e não foi medido.

O que o ranking mostra: o embedding pega a entidade e não o assunto. Em "Qual o lead time de verdade da Katrina?", o top 10 é quase todo sobre a Katrina, mas o `#relacionamento` e o `#contato-comercial` aparecem antes do `contrato#clausulas-comerciais/3-prazos`, que fica fora do top 15 porque fala em "antecedência mínima de 45 dias" e não em "lead time". Trocar pelo mpnet não resolve (+4 pontos), e o corpus tem só 79 trechos, então o top 10 já é 13% dele.

Opções para decidir:
1. Aumentar o `k` padrão da busca e deixar o Jev filtrar mais. Com 79 trechos, k = 20 a 25 custa 2 a 2,5 vezes mais requests por busca.
2. Revisar os rótulos. Alguns casos marcam muitos trechos como relevantes (c07 marca 5, sendo 3 de mercado de algodão), e isso puxa o recall para baixo.
3. Rever o critério de 0,9 na spec, ou trazer a busca híbrida (BM25 + vetor), que hoje está fora de escopo.

**2026-09-30 (agente):** o dev escolheu a opção 1. Recall por k com o MiniLM: @20 0,745, @25 0,830, @30 0,915, @40 1,0. A busca passa a recuperar k = 30 por padrão e o critério vira recall@30 >= 0,9 (registrado na ADR-0004). `scripts/avaliar_recuperacao.py` agora mede @10, @20 e @30. O `k` do endpoint no ticket 04 vai de 1 a 40 em vez de 1 a 20.
