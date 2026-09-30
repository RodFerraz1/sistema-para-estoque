# 01: Faixa de aprovação e pedido de compra no ERP fake

**Status:** done
**Blocked by:** M6 concluído
**Spec:** `.scratch/aprovacao/spec.md` (seções "Faixa de aprovação" e "Escrita no ERP fake")
**ADR:** `docs/adr/0003-politica-de-compra-configuravel.md`

## What to build

A política de compra ganha os limites das faixas de aprovação, e o `purchasing` calcula a faixa de um pedido com as exceções do documento de aprovação. O `ERPAdapter` ganha a única escrita do Copilot no ERP: criar pedido de compra `aprovado`, chamado por `purchasing.submeter_pedido`.

## Acceptance criteria

- [x] `faixa_1_ate_reais`, `faixa_2_ate_reais`, `faixa_3_ate_reais` em `ParametrosPolitica` (com validação de ordem), migration `0006` com os padrões do documento, `GET/PUT /politica-compra` com os campos.
- [x] `purchasing.faixa_aprovacao` e `FaixaAprovacao` com as regras da spec.
- [x] `ERPAdapter.criar_pedido_compra`, `ItemNovoPedido` e `ERPAdapter.fornecedor_tem_pedido`, em Postgres e in-memory, com teste de contrato.
- [x] `purchasing.submeter_pedido` com as validações, a data prevista e a observação da spec.
- [x] Testes da spec.
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Parâmetros**: `faixa_1_ate_reais`, `faixa_2_ate_reais` e `faixa_3_ate_reais` em `ParametrosPolitica`, obrigatórios como os outros campos (o `PUT /politica-compra` passa a exigi-los), com `faixa_1 > 0` e `faixa_1 < faixa_2 < faixa_3`. `PARAMETROS_V1` ganhou 15.000, 60.000 e 150.000. A migration `0006_faixas_aprovacao` adiciona as colunas com esses valores como `server_default`, para preencher as versões existentes, e depois tira o default: como nas outras colunas da política, quem grava informa o valor. Upgrade e downgrade testados no Postgres local.
- **Assinatura da faixa** (desvio da spec, que listava `faixa_aprovacao(sku_code, fornecedor_id, quantidade, valor_centavos, alertas)`): a função pura é `src/purchasing/faixa.py::faixa_aprovacao(valor_centavos, *, viola_teto, fornecedor_tem_pedido, parametros) -> FaixaAprovacao`, só com o que a regra usa. O serviço expõe `Purchasing.faixa_aprovacao(sugestao, quantidade=None)`, que junta a política ativa e o histórico do fornecedor. É o que o ticket 02 chama, porque a `Aprovacao` não depende de `erp_adapter` nem de `politica_compra`.
- **Quantidade editada**: `Purchasing.faixa_aprovacao` recalcula o valor e também a violação de teto. Vale o alerta `viola_teto` da sugestão ou a cobertura na chegada, com a quantidade nova, acima do teto da política ativa. Sem isso, o comprador poderia multiplicar a quantidade e continuar descendo uma faixa como reposição regular. Com a quantidade sugerida e a mesma política, o resultado bate com o alerta. A quantidade é validada como no `submeter_pedido`.
- **Política usada na faixa**: a ativa no momento do cálculo, não a `politica_versao` da sugestão (o port do repositório só tem `ativa()`). Na geração da fila as duas coincidem; na aprovação com edição vale a regra em vigor quando o comprador aprova.
- **`ajustes`**: uma frase por exceção que mudou a faixa. A reposição regular na faixa 1, a violação na faixa 4 e o fornecedor sem pedido já na faixa 3 ou 4 não geram frase. Ordem de aplicação: faixa pelo valor, depois reposição (desce) ou violação (sobe), depois o mínimo 3 do fornecedor sem pedido.
- **`purchasing` fala com o `ERPAdapter`**: o `Purchasing` recebe o adapter no construtor (`Purchasing(ficha_sku, inventory, sales, politicas, erp, *, now=None)`), só para pedido de compra (`fornecedor_tem_pedido` e `criar_pedido_compra`), que não tem módulo de leitura próprio. A docstring do módulo dizia que ele não falava com o adapter e foi atualizada.
- **`ItemNovoPedido`** fica em `src/purchasing/schemas.py`, como os DTOs que o port já importa de `catalog`, `inventory` e `sales`, com `quantidade > 0` e `preco_unitario_centavos >= 0` validados no DTO. O `criar_pedido_compra` lança `ValueError` sem itens ou com fornecedor ou SKU inexistente, sem gravar nada. Os adapters gravam `valor_total_reais` e `preco_unitario_reais` em centavos, como o seed; os campos novos do espelho in-memory (`valor_total_centavos`, `preco_unitario_centavos`, `aprovado_em`, `observacao`) seguem a unidade real.
- **Contrato**: `src/erp_adapter/tests/test_contrato_pedido_compra.py` roda contra in-memory e Postgres. O port não tem leitura de pedido, então cada cenário traz o próprio `ler_pedido`, que olha as linhas gravadas. Não criei `carregar_pedido_compra` no port por não ter consumidor. O cenário Postgres cria fornecedor e SKUs próprios e apaga tudo no teardown.
- **`submeter_pedido`**: lança `SugestaoSemCompra` (sugestão sem fornecedor ou sem cálculo), `QuantidadeInvalida` (zero, negativa ou abaixo do MOQ; o ticket 02 mapeia para 422) e `ValueError` com `aprovado_por` vazio. Ambas as exceções herdam de `ValueError` e ficam em `src/purchasing/service.py`, como o `SKUSemEstoque` do `ficha_sku`. A data prevista usa a data em UTC do relógio do serviço, como o resto do `purchasing`.
- **Seed**: com os limites do documento, as sugestões do seed ficam bem abaixo de R$ 15.000 (a de `TBC-BEGE-70140-01` dá 261 unidades e R$ 4.452,66, faixa 1). Na fila do ticket 02, a justificativa só vai aparecer com fornecedor sem pedido anterior, violação de teto ou quantidade editada para cima.
- **Fora do escopo, sem mexer**: o contexto da intenção de política no chat (`ai/contexto.py::_politica`) não mostra os limites das faixas. Fica para quando o chat precisar responder sobre aprovação.
- **`CONTEXT.md`**: verbete novo "Faixa de aprovação"; "Política de compra" passa a listar os limites das faixas.
- **Testes**: `uv run pytest -q -m "not externo"` com 625 passando (eram 561).
