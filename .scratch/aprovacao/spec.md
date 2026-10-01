---
Status: ready-for-agent
Escopo: M7 do roadmap (aprovação humana: fila de sugestões, pedido no ERP fake, UI e onboarding)
Vocabulário: ver /CONTEXT.md
Decisões arquiteturais base: /docs/adr/0001-monolito-modular-por-dominio.md, /docs/adr/0002-jev-decide-codigo-executa-llm-redige.md, /docs/adr/0003-politica-de-compra-configuravel.md
Depende de: M6 (`.scratch/sinais-e-citacoes/spec.md`)
Origem: decisões do agente em 2026-09-30, com o dev AFK e autonomia total delegada
---

# Spec 07 - Aprovação humana: fila de sugestões, pedido no ERP e UI

## Problem Statement

Até o M6, o Copilot sugere e explica, mas nada vira pedido. O comprador chefe precisa, SKU a SKU, pedir a sugestão, conferir e digitar o pedido no ERP. Falta o fim do fluxo que é premissa do Copilot: ele sugere, o humano aprova, o pedido aparece no ERP (CONTEXT.md: "sempre com humano aprovando no fim").

Também falta uma interface. Tudo é JSON por HTTP, o que não serve para o comprador chefe. E a política de compra ainda carrega chutes do desenvolvedor, porque ninguém respondeu `perguntas-comprador.md`: o onboarding previsto na ADR-0003 não existe.

Por fim, a política de aprovação do corpus (`politicas/aprovacao-compras.md`) define faixas de valor com aprovadores diferentes, e hoje nada no sistema calcula a faixa de um pedido.

## Solution

1. **Faixa de aprovação** (`purchasing`, determinística): faixa 1 a 4 pelo valor do pedido, com os limites como parâmetros da política de compra e as exceções do documento como mecanismo (reposição regular desce uma faixa, violação de teto sobe uma, fornecedor sem pedido anterior vai no mínimo para a 3).
2. **Escrita no ERP fake**: `ERPAdapter.criar_pedido_compra` e `purchasing.submeter_pedido`, que cria o pedido com status `aprovado`. É a única escrita do Copilot no ERP, e só a aprovação humana chama.
3. **Fila de aprovação** (módulo novo `aprovacao`): gera sugestões para todos os SKUs ativos, guarda as que têm quantidade, anexa os sinais do corpus, prioriza (destaque pelos motivos que o comprador escolhe na política, depois urgência) e registra a decisão humana (aprovar, com quantidade editável, ou rejeitar).
4. **UI mínima** servida pelo próprio FastAPI em `/ui`: fila de aprovação, chat e onboarding da política.

## User Stories

### Comprador chefe

1. Como comprador chefe, quero apertar um botão e ver a fila de sugestões de compra de todos os SKUs que precisam de reposição, para não pedir SKU a SKU.
2. Como comprador chefe, quero ver no topo da fila as sugestões com alerta (ruptura, teto, prazo, sinais do corpus), para olhar primeiro o que é arriscado.
3. Como comprador chefe, quero aprovar uma sugestão, com a quantidade que ela trouxe ou com outra que eu digitar, e ver o pedido criado no ERP, para não redigitar.
4. Como comprador chefe, quero rejeitar uma sugestão com um motivo, para ela sair da fila e o motivo ficar registrado.
5. Como comprador chefe, quero ver a faixa de aprovação de cada pedido e quem precisa aprovar, para seguir a política de aprovação.
6. Como comprador chefe, quero ser obrigado a escrever uma justificativa quando o pedido é da faixa 2 ou acima, porque a política pede justificativa em ata.
7. Como comprador chefe, quero responder as perguntas de onboarding numa tela, na minha linguagem, e ver a política ganhar uma versão nova, para o Copilot parar de usar os chutes do desenvolvedor.
8. Como comprador chefe, quero conversar com o Copilot numa tela, vendo a resposta, o que ele entendeu e as fontes.

### Desenvolvedor

9. Como desenvolvedor, quero que só um endpoint de aprovação humana consiga criar pedido no ERP, para a divisão por risco da `module-interfaces.md` valer no código.
10. Como desenvolvedor, quero a faixa de aprovação como função pura sobre a sugestão, a política e o histórico do fornecedor, para testar as exceções uma a uma.
11. Como desenvolvedor, quero a UI sem build (HTML, CSS e JS puros), para não trazer um segundo ecossistema ao projeto.

## Implementation Decisions

### Faixa de aprovação

**Parâmetros novos da política** (ADR-0003: parâmetro novo é coluna tipada com padrão): `faixa_1_ate_reais = 15000`, `faixa_2_ate_reais = 60000`, `faixa_3_ate_reais = 150000` (valores de `politicas/aprovacao-compras.md` v2, em reais inteiros). Migration `0006` adiciona as colunas em `copilot.politicas_compra` com esses padrões (as versões existentes ganham os valores do documento). Validação: `faixa_1 < faixa_2 < faixa_3`. `GET/PUT /politica-compra` passam a ter os três campos.

**Cálculo** (função pura `purchasing/faixa.py::faixa_aprovacao(valor_centavos, *, viola_teto, fornecedor_tem_pedido, parametros) -> FaixaAprovacao`; o serviço expõe `Purchasing.faixa_aprovacao(sugestao, quantidade=None)`, que passa o histórico do fornecedor e os parâmetros da **versão da política com que a sugestão foi gerada** (`politica_versao`, via `Purchasing.politica_da`), coerente com o resto da sugestão; uma política salva depois não muda a faixa de sugestões já na fila):

1. Faixa base pelo valor: até `faixa_1_ate_reais` é 1; até `faixa_2` é 2; até `faixa_3` é 3; acima é 4 (limites inclusivos, em centavos na comparação).
2. Reposição regular: se a sugestão não tem alerta `viola_teto`, desce uma faixa (mínimo 1). Toda sugestão do Copilot é reposição de SKU com histórico (SKU novo não gera quantidade), então a exceção vale sempre que não há violação.
3. Violação de política: com alerta `viola_teto`, sobe uma faixa (máximo 4).
4. Fornecedor sem pedido anterior no ERP (fora `rascunho` e `cancelado`): no mínimo faixa 3.

`FaixaAprovacao`: `faixa: int`, `aprovadores: str`, `exige_justificativa: bool` (faixa >= 2), `ajustes: list[str]` (frases das exceções aplicadas). Aprovadores (texto fixo do documento): 1 "comprador chefe"; 2 "comprador chefe + gerente comercial ou sócio financeiro"; 3 "comprador chefe + gerente comercial + sócio financeiro"; 4 "comprador chefe + gerente comercial + sócio financeiro, com reunião de compra registrada".

Limitação registrada: o documento avalia o valor com impostos e frete, e o ERP fake não tem nenhum dos dois. A faixa usa o valor dos itens.

### Escrita no ERP fake

- `ERPAdapter.criar_pedido_compra(fornecedor_id, itens: list[ItemNovoPedido], data_prevista_entrega: date, observacao: str) -> UUID` com `ItemNovoPedido(sku_code, quantidade, preco_unitario_centavos)` em `erp_adapter/schemas.py` (o `purchasing` importa do `erp_adapter`, nunca o contrário). Cria `erp.pedidos_compra` com status `aprovado`, `aprovado_em` agora e `valor_total_reais` (centavos, como o resto da tabela) somado dos itens, e um `erp.pedidos_compra_itens` por item. Uma transação. Postgres e in-memory, com teste de contrato.
- `ERPAdapter.fornecedor_tem_pedido(fornecedor_id) -> bool`: existe pedido fora de `rascunho` e `cancelado`.
- `purchasing.submeter_pedido(sugestao: SugestaoPedido, quantidade: int, aprovado_por: str, referencia: str) -> UUID`: valida quantidade > 0 e >= MOQ do fornecedor, calcula `data_prevista_entrega = hoje + calculo.lead_time_dias` e grava com a observação "Criado pelo Copilot a partir da sugestão <referencia>, aprovado por <aprovado_por>." Depois disso o pedido conta como em trânsito, e a próxima sugestão do SKU já o desconta.

### Fila de aprovação (módulo `aprovacao`)

Módulo novo `src/aprovacao/` (depende de `catalog`, `purchasing` e `ai`; nada depende dele além da `api`). Tabela `copilot.sugestoes_fila` (migration `0007`), atrás do port `SugestoesFilaRepositorio`: `id uuid PK`, `criado_em`, `sku_code`, `status text` (`pendente`, `aprovada`, `rejeitada`, `substituida`), `destaque boolean`, `cobertura_na_chegada_sem_compra_meses double precision`, `dados jsonb` (a `SugestaoComSinais` e o `SKU`), `faixa jsonb` (a `FaixaAprovacao`), `decidido_em`, `decidido_por`, `quantidade_aprovada integer null`, `justificativa text null`, `motivo_rejeicao text null`, `pedido_compra_id uuid null`. Índice em `(status, destaque DESC, cobertura_na_chegada_sem_compra_meses)`.

Serviço `Aprovacao`:

- `gerar_fila() -> ResultadoGeracao`: `sugerir_pedido` para cada SKU ativo (`catalog.listar_skus`), fica com as de quantidade > 0, calcula os sinais com `SinaisCorpus.para_sugestoes` (um cálculo por par fornecedor e produto) e a faixa. **Todas** as pendentes anteriores viram `substituida` (não só as do mesmo SKU), para a fila refletir os dados de agora: um SKU que deixou de precisar de compra também sai. `DecisaoIndisponivel` nos sinais não impede a geração: as sugestões entram sem sinais e o resultado avisa. `ResultadoGeracao`: `geradas`, `substituidas`, `skus_avaliados`, `sinais_indisponiveis: bool`.
- `destaque` = tem algum alerta do `purchasing` ou sinal do corpus que esteja nos **motivos de destaque** da versão da política da sugestão. `motivos_de_destaque` é parâmetro da política (ADR-0003; migration `0008_motivos_de_destaque`, coluna `text[]` com check dos valores, versões existentes preenchidas com o padrão), uma lista dos tipos de alerta (`TipoAlerta`) e de sinal (`TipoSinal`), com pergunta de onboarding. Padrão: `ruptura_antes_da_chegada` e `viola_teto`. Motivo: com todos os alertas de risco e sinais, a geração real contra o seed destacava 30 de 31 (26 de 31 sem o Jev), e o destaque não separava nada; com o padrão, 10 de 31, com ou sem o Jev. Medido nas gerações gravadas do seed: ruptura 9, teto 1, lead time observado acima do contratado 21, atraso do fornecedor 7, encalhe 6, demanda sazonal 1; acrescentar o atraso dá 15 de 31, os três sinais 18, o lead time 26. Lista vazia é válida (fila só pela urgência). Ordem da fila: destaque primeiro, depois `cobertura_na_chegada_sem_compra_meses` crescente (`MemoriaCalculo.cobertura_na_chegada_sem_compra_meses`, a cobertura quando a compra chega sem contar a compra, negativa quando o estoque acaba antes; a `cobertura_na_chegada_meses` já inclui a compra e não mede urgência), e o `sku_code` para desempatar. A confiança e os sinais só ordenam, nunca aprovam (roadmap).
- `listar(status="pendente") -> list[SugestaoNaFila]` na ordem da fila; `carregar(id)`.
- `aprovar(id, aprovado_por, quantidade=None, justificativa=None) -> SugestaoNaFila`: **reserva** a sugestão antes de chamar o ERP (`SugestoesFilaRepositorio.decidir(id, decisao)`: `SELECT ... FOR UPDATE` da linha no Postgres, uma trava no in-memory). Com a reserva: só `pendente` (senão `SugestaoJaDecidida`); recalcula a faixa com a quantidade aprovada e a versão da política da sugestão; faixa que exige justificativa sem justificativa vira `JustificativaObrigatoria`; chama `purchasing.submeter_pedido` e grava `aprovada` com `pedido_compra_id`, na mesma transação. Uma segunda aprovação simultânea espera a primeira e recebe `SugestaoJaDecidida` sem criar pedido. Se o ERP falha (ou o processo cai), a transação volta e a sugestão continua `pendente`. Sobra uma janela: o pedido gravado no ERP e a gravação da fila falhando depois (as duas bases não têm transação comum).
- `faixa_para(id, quantidade) -> FaixaAprovacao`: a faixa que a aprovação teria com essa quantidade, sem decidir nada, para a UI avisar da justificativa antes de enviar.
- `rejeitar(id, rejeitado_por, motivo) -> SugestaoNaFila`: só `pendente`; motivo obrigatório.

Endpoints (`src/api/aprovacao.py`): `POST /sugestoes/gerar`; `GET /sugestoes?status=pendente`; `GET /sugestoes/{id}`; `GET /sugestoes/{id}/faixa?quantidade=N` (a `FaixaAprovacao` da quantidade, 404 e 422 como na aprovação); `POST /sugestoes/{id}/aprovar` (corpo `aprovado_por`, `quantidade` opcional, `justificativa` opcional); `POST /sugestoes/{id}/rejeitar` (corpo `rejeitado_por`, `motivo`). 404 para id inexistente, 409 para sugestão já decidida, 422 para quantidade abaixo do MOQ ou justificativa faltando. `POST /sugestoes/gerar` com Jev fora do ar responde 200 com `sinais_indisponiveis: true`.

### UI

Arquivos estáticos em `src/ui/` servidos com `StaticFiles` em `/ui` (`/` redireciona para `/ui/`). HTML, CSS e JS puros, sem build, sem framework, `fetch` para a API. Português, layout simples e legível no celular. Três páginas com um menu comum:

- **Fila** (`/ui/index.html`): botão "Gerar sugestões" (mostra o resultado da geração); cards das pendentes na ordem da fila, com SKU, produto, fornecedor, quantidade, valor, cobertura na chegada, faixa e aprovadores, alertas e sinais (com os ids dos trechos), destaque visual para `destaque`. Aprovar abre um formulário com nome, quantidade (preenchida com a sugerida) e justificativa (obrigatória quando a faixa exige). Mudar a quantidade consulta `GET /sugestoes/{id}/faixa` e mostra a faixa nova, com a justificativa passando a obrigatória quando for o caso, antes de enviar. Rejeitar pede nome e motivo. Depois da aprovação, o card mostra o id do pedido criado. Um filtro mostra as aprovadas e as rejeitadas.
- **Chat** (`/ui/chat.html`): caixa de pergunta e a resposta em texto, com a intenção, a confiança, a faixa, os SKUs, os trechos usados e as citações com o veredito. Esclarecimento e confirmação aparecem como resposta normal.
- **Política** (`/ui/politica.html`): o onboarding. As perguntas 1 a 9 de `.scratch/sugestao-compra/perguntas-comprador.md` com a linguagem do comprador, cada uma preenchida com o valor atual (`GET /politica-compra`), mais uma pergunta para os limites das faixas de aprovação e uma para os motivos de destaque da fila. Salvar faz `PUT /politica-compra` e mostra a versão nova ou o erro de validação. As perguntas 10 a 14 aparecem como "como o sistema entende o ERP", só leitura.

Testes da UI: HTTP (as páginas e os assets respondem 200 com o tipo certo) e um teste que confere que todo endpoint chamado pelos `.js` existe no app (lê os caminhos com regex e compara com as rotas do FastAPI).

## Testing Decisions

- **`faixa_aprovacao`**: cada limite (inclusivo), a descida por reposição, a subida por teto, o mínimo 3 para fornecedor novo, os limites 1 e 4 não passam.
- **`criar_pedido_compra` e `fornecedor_tem_pedido`**: contrato contra in-memory e Postgres (pedido e itens gravados, valor somado, status `aprovado`, entra em `itens_em_transito_de`).
- **`submeter_pedido`**: MOQ, quantidade zero, data prevista, observação.
- **`Aprovacao`**: geração (só quantidade > 0, substitui pendentes, sinais uma vez por par, Jev fora do ar), ordem da fila, aprovar (com e sem edição, justificativa por faixa, já decidida), rejeitar. Adapters em memória.
- **Repositório da fila**: contrato contra in-memory e Postgres, incluindo a reserva (`decidir` simultâneo espera o primeiro; decisão que falha não grava e solta a reserva).
- **HTTP**: cada endpoint com os códigos da spec.
- **Smoke**: gerar a fila contra o seed, aprovar a primeira pendente e ver o pedido no ERP e a sugestão seguinte do mesmo SKU descontando o em trânsito. No fim, apaga só as linhas da fila e os pedidos que ele criou e devolve para `pendente` as que ele substituiu.

## Out of Scope

- Agrupar SKUs do mesmo fornecedor num pedido (pós-MVP no roadmap). Cada sugestão aprovada vira um pedido de um item.
- Autenticação e papéis: o nome de quem aprova é informado, não verificado. A faixa mostra quem precisa aprovar, mas o sistema não coleta as aprovações dos outros papéis.
- Impostos e frete no valor da faixa.
- Enviar o pedido ao fornecedor, receber mercadoria, cancelar pedido.
- Histórico de versões da política na tela.

## Further Notes

- Gerar a fila avalia os 80 SKUs do seed. Os sinais são por par (fornecedor, produto), uns 20 pares, cada um com uma busca focada e até 10 requests de sinais: uns 800 requests do Jev (menos de US$ 0,02) e algo entre 30 e 60 s. A geração é uma ação explícita do comprador, não roda a cada listagem.
- Ordem dos tickets: 01 (faixa e escrita no ERP), 02 (fila), 03 (UI), 04 (README e smoke).
