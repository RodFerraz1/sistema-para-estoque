# Roadmap - Do zero até MVP

Sequência de milestones. Cada um é um "hello world" mais completo que o anterior, sempre entregando algo *rodando end-to-end*. Não é fazer todo o schema, depois todo o adapter, depois todo o AI. É montar a *fatia mais fina possível* atravessando todas as camadas, e engordar.

Cada milestone é um bloco de trabalho de 1 sessão a 2-3 dias. Você marca como concluído antes de passar pro próximo.

## M0 - Fundação (só infra e Hello World)

- Repositório Python configurado (`pyproject.toml` com `uv` ou `poetry` - escolher no M0).
- `docker-compose.yml` com Postgres + pgvector.
- FastAPI rodando com endpoint `/health` que retorna `{"status": "ok"}`.
- README com "como rodar localmente".

**Saída visível**: `curl http://localhost:8000/health` funciona.

## M1 - ERP fake com dados

- Schema `erp` criado no Postgres (migration com Alembic).
- Todas as 9 tabelas do `erp-schema.md` criadas.
- Script `seed.py` que popula ~15 produtos, ~80 SKUs, 5 fornecedores, ~180 relações, 2 anos de vendas e movimentações plausíveis, estoque atual coerente.
- Endpoint `/erp/skus/{id}` que retorna dados crus de um SKU. Só pra confirmar que dados chegam.

**Saída visível**: você consegue consultar um SKU e ver dados populados.

## M2 - Primeira leitura útil (giro e cobertura)

- Módulo `erp_adapter` com implementação Postgres.
- Módulos `catalog`, `inventory`, `sales` com as interfaces mínimas: `get_sku`, `estoque_atual`, `cobertura_meses`, `giro_medio_mensal`.
- Endpoint `/skus/{id}/analise` que retorna JSON com nome do SKU + estoque atual + giro + cobertura.

**Saída visível**: você digita um SKU e vê a foto de estoque dele. Nenhuma IA envolvida ainda.

## M3 - Sugestão determinística (sem IA)

- Módulo `purchasing.sugerir_pedido` implementado sem LLM.
- Regras: pega fornecedor mais barato, calcula quantidade pra levar cobertura pra 3 meses (piso da política), respeita MOQ do fornecedor.
- Aplica política (checa teto de estoque, alerta se violação).
- Endpoint `/skus/{id}/sugerir-compra` retorna `SugestaoPedido` completa em JSON.

**Saída visível**: pergunta "quanto comprar do SKU X?" e recebe sugestão estruturada, sem envolver LLM.

**Ponto de reflexão**: nesta altura você já tem um sistema *útil* sem IA. Isso é intencional - se a IA falhar depois, o sistema ainda funciona. IA é aumento de valor, não fundação.

## M4 - RAG básico

- Módulo `ai` com componente RAG: pipeline de ingestão dos 11 documentos seed, chunking, embedding (via API - `text-embedding-3-small` da OpenAI, ~2 centavos pro corpus todo), gravação em pgvector.
- Função `ai.buscar_contexto(query, k=5)` que retorna trechos relevantes.
- Endpoint `/rag/busca?q=...` que retorna trechos brutos. Ainda sem LLM gerando resposta.

**Saída visível**: pesquisa "lead time da Katrina" e vê os trechos dos documentos relevantes.

## M5 - Primeira conversa com LLM + tool use de leitura

- Cliente Groq configurado.
- Endpoint `/chat` recebe pergunta em linguagem natural, LLM tem acesso a 5-6 tools de leitura (`get_sku`, `estoque_atual`, `giro_medio_mensal`, `cobertura_meses`, `buscar_contexto`).
- LLM decide qual tool chamar, você vê no log.
- Resposta em texto pra pergunta tipo "qual a situação do SKU TBC-BEG-70140?".

**Saída visível**: você conversa com o Copilot sobre um SKU e ele responde usando dados reais.

## M6 - Sugestão via LLM (tool call para `sugerir_pedido`)

- `purchasing.sugerir_pedido` exposta como tool do LLM.
- LLM decide quando invocar - ex: pergunta "devo comprar do SKU X?" faz ele chamar `sugerir_pedido` e explicar o resultado.
- Resposta cita documentos do RAG quando relevante ("segundo a política de estoque...").

**Saída visível**: pergunta livre em linguagem natural e resposta rica combinando dados + sugestão + contexto do RAG.

## M7 - Aprovação humana (workflow completo)

- UI mínima (HTML puro ou React simples) com: lista de sugestões pendentes, botão aprovar/rejeitar/editar.
- `purchasing.submeter_pedido` só é acionado por endpoint que exige aprovação.
- Sugestão aprovada vira `pedido_compra` no ERP fake com status `aprovado`.

**Saída visível**: workflow end-to-end. LLM sugere, você aprova, aparece no ERP.

## M8 - Refinamentos e apresentabilidade

- Trocar Groq por Claude/GPT no deploy final (chave em env var).
- Melhorar prompts com base em observação real.
- README com fluxo, screenshots, arquitetura desenhada.
- Vídeo de demo curto.

**Saída visível**: projeto de portfólio publicável.

## Depois do MVP (fora do escopo agora)

- Quebrar `ai` em microserviço separado (aí faz sentido).
- Substituir ERP fake por integração real (quando/se der).
- Deploy real (Fly.io, Railway, ou AWS - decidir depois).
- Métricas de retrieval quality (RAGAs, etc).
- Fine-tuning ou avaliação sistemática.

## Onde marcar progresso

Cada milestone vira um issue file em `.scratch/copilot-compras/issues/NN-<slug>.md` conforme convenção do issue tracker local (ver `docs/agents/issue-tracker.md`). O primeiro que abrimos é `01-fundacao.md` quando começar M0.
