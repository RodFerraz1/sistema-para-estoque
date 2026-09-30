# Embeddings locais com fastembed

Status: accepted (2026-09-29)

A busca vetorial do RAG usa um modelo de embedding que roda dentro do próprio processo, via `fastembed` (ONNX, sem PyTorch). O modelo inicial é o `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões, ~220 MB), multilíngue e bom em português. O embedder fica atrás de um port no `ai`, como o Jev e o redator.

Escolhemos isso porque o Copilot já depende de dois provedores de IA (Jev e o redator), e um terceiro só para embedding traria mais uma chave, mais uma conta e mais um ponto de falha. O corpus é pequeno (algumas centenas de trechos) e a busca vetorial é só a primeira peneira, porque quem decide a relevância é o Jev (ADR-0002). O que importa na busca vetorial é o recall no top-k, e isso um modelo local pequeno entrega.

## Considered Options

- **OpenAI `text-embedding-3-small` (plano original do roadmap)**: rejeitada. Terceiro provedor de IA e exige `OPENAI_API_KEY` só para embedding.
- **`intfloat/multilingual-e5-large` ou `Qwen3-Embedding-0.6B` locais**: adiadas. São melhores, mas pesam mais de 2 GB. Viram a troca natural se o MiniLM não atingir o recall exigido na spec 04.

## Consequences

- A dimensão do vetor (384) fica fixa na coluna `vector(384)`. Trocar de modelo exige migration e reingestão do corpus.
- A imagem Docker cresce uns 220 MB, porque o modelo é baixado no build para o app não depender de download em runtime.
- A qualidade da busca é medida pelo recall@k contra os casos rotulados em `evals/`, e não assumida.
- **2026-09-30**: o MiniLM deu recall@10 de 0,53 contra os casos de `evals/casos.json` (o `paraphrase-multilingual-mpnet-base-v2` deu 0,57). O modelo pega a entidade e não o assunto: em "lead time da Katrina", a cláusula de prazos do contrato fica fora do top 15 porque fala em "antecedência mínima". Em vez de trocar de modelo, a busca recupera k = 30 por padrão (recall@30 de 0,92) e o Jev filtra. O critério passa a ser recall@30 >= 0,9. Se o corpus crescer e esse recall cair, a troca de modelo volta à mesa.
