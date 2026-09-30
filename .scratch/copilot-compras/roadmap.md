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

Spec: `.scratch/sugestao-compra/spec.md`. Decisão base: ADR-0003 (mecanismo fixo, parâmetros do comprador).

- Política de compra versionada no schema `copilot`, editável via `GET/PUT /politica-compra`. A v1 usa os valores da política v3 do corpus.
- `inventory.em_transito`: o que falta chegar de pedidos de compra abertos.
- `purchasing.sugerir_pedido` sem LLM: posição com em trânsito, estoque na chegada descontando o lead time, ponto de reposição, MOQ, escolha de fornecedor pelo critério da política, teto e alertas.
- Endpoint `/skus/{sku_code}/sugestao-compra` retorna `SugestaoPedido` em JSON, com quantidade zero e motivo quando não há compra.

**Saída visível**: pergunta "quanto comprar do SKU X?" e recebe sugestão estruturada, sem envolver LLM.

**Ponto de reflexão**: nesta altura você já tem um sistema *útil* sem IA. Isso é intencional - se a IA falhar depois, o sistema ainda funciona. IA é aumento de valor, não fundação.

**Concluído em 2026-09-29.**

## Divisão de papéis na IA (M4 em diante)

A partir do M4 o `ai` segue a ADR-0002: **Jev decide, código executa, LLM redige**. O Jev (TypeSafe) responde perguntas tipadas (`Choice`, `Score`, `Noul`) com confiança, o código roteia e faz as contas, e o LLM só escreve a resposta final. Número, contagem e data nunca vão para o Jev.

## M4 - Spike do Jev + RAG com filtro de trechos

Spec: `.scratch/rag-jev/spec.md`. Decisões base: ADR-0002 (Jev decide) e ADR-0004 (embeddings locais).

- **Spike primeiro (gate da ADR-0002)**: rodar o Jev em português contra o corpus e umas 20 perguntas típicas do comprador. Medir acerto de intenção, acerto de relevância de trecho, custo e latência. Se não passar, reabrir a ADR-0002 antes de seguir.
- Módulo `ai` com port `DecisionModel` (adapter Jev + adapter in-memory pra teste).
- Pipeline de ingestão dos 11 documentos seed: chunking, embedding local com fastembed (ADR-0004), gravação em pgvector.
- `ai.buscar_contexto(query, k)`: busca vetorial seguida de um filtro com o Jev, que pergunta por trecho se é relevante, se contradiz outro trecho e se tenta dar instrução ao modelo. Devolve trechos classificados como aceito, conflitante ou descartado.
- Endpoint `/rag/busca?q=...` que retorna os trechos com a classificação e a confiança.

**Saída visível**: pesquisa "lead time da Katrina" e vê os trechos relevantes, com o conflito entre lead time contratual e observado sinalizado.

**Concluído em 2026-09-30.** O gate da ADR-0002 reprovou na relevância de trecho, e o dev manteve a ADR aceitando o risco (`.scratch/rag-jev/spike-resultado.md`).

## M5 - Primeira conversa: Jev roteia, LLM redige

- Endpoint `/chat` recebe pergunta em linguagem natural.
- Jev classifica a intenção com um `Choice` (situação do SKU, pergunta sobre política ou fornecedor, pedido de sugestão, fora de escopo) e extrai o `sku_code` quando houver.
- Roteamento com confiança: alta executa, média executa e pede confirmação, baixa pede esclarecimento ao comprador.
- Código chama os leitores (`ficha_sku.completa`, `buscar_contexto`) conforme a intenção.
- Cliente Groq configurado **só como redator**: recebe os dados montados e escreve a resposta. Não tem tools.
- Log de cada decisão do Jev (pergunta, resposta, confiança) pra auditoria.

**Saída visível**: "qual a situação do SKU TBC-BEG-70140?" gera resposta em texto, e o log mostra a intenção escolhida e a confiança.

## M6 - Sugestão com sinais do corpus

- Intenção "pedido de sugestão" leva o código a chamar `purchasing.sugerir_pedido` (determinístico, do M3).
- Jev extrai sinais qualitativos do corpus sobre o SKU e o fornecedor sugerido, por exemplo um `Score` de confiabilidade do fornecedor segundo as reuniões e um `Noul` de evento sazonal relevante. Os sinais viram alertas anexados à `SugestaoPedido` e não alteram a quantidade calculada.
- LLM redige a explicação citando os documentos.
- Jev confere se cada citação da resposta é sustentada pelo trecho citado. Citação sem suporte é removida ou sinalizada.

**Saída visível**: pergunta livre gera resposta que combina dados, sugestão e contexto do RAG, com citações verificadas.

## M7 - Aprovação humana (workflow completo)

- UI mínima (HTML puro ou React simples) com: lista de sugestões pendentes, botão aprovar/rejeitar/editar.
- Sugestões com alertas do Jev ou baixa confiança aparecem destacadas no topo da fila. A confiança só prioriza, nunca aprova.
- `purchasing.submeter_pedido` só é acionado por endpoint que exige aprovação.
- Sugestão aprovada vira `pedido_compra` no ERP fake com status `aprovado`.
- Tela de onboarding que preenche a política de compra, a partir de `.scratch/sugestao-compra/perguntas-comprador.md`.
- Faixa de aprovação (`politicas/aprovacao-compras.md`) calculada sobre o pedido inteiro.

**Saída visível**: workflow end-to-end. Copilot sugere, você aprova, aparece no ERP.

## M8 - Refinamentos e apresentabilidade

- Trocar o redator Groq por Claude/GPT no deploy final (chave em env var).
- Ajustar perguntas do Jev e thresholds de confiança com base no log de decisões.
- Melhorar prompt do redator com base em observação real.
- README com fluxo, screenshots, arquitetura desenhada.
- Vídeo de demo curto.

**Saída visível**: projeto de portfólio publicável.

## Depois do MVP (fora do escopo agora)

- Quebrar `ai` em microserviço separado (aí faz sentido).
- Substituir ERP fake por integração real (quando/se der).
- Deploy real (Fly.io, Railway, ou AWS - decidir depois).
- Métricas de retrieval quality (RAGAs, etc).
- Fine-tuning ou avaliação sistemática.
- Modo `ajustar` da sazonalidade na política de compra, com `sales.previsao_venda`.
- Sugestão em lote e agrupamento de SKUs por fornecedor num mesmo pedido.

## Onde marcar progresso

Cada milestone vira um issue file em `.scratch/copilot-compras/issues/NN-<slug>.md` conforme convenção do issue tracker local (ver `docs/agents/issue-tracker.md`). O primeiro que abrimos é `01-fundacao.md` quando começar M0.
