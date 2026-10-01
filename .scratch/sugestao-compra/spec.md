---
Status: done
Escopo: M3 do roadmap (sugestão de pedido determinística, sem IA)
Vocabulário: ver /CONTEXT.md
Decisões arquiteturais base: /docs/adr/0001-monolito-modular-por-dominio.md, /docs/adr/0003-politica-de-compra-configuravel.md
Origem: grilling de 2026-09-25
---

# Spec 03 - Sugestão de pedido com política de compra configurável

## Problem Statement

Com o M2 pronto, o comprador chefe consegue ver a ficha de um SKU (estoque, giro, cobertura, fornecedores), mas a pergunta que ele realmente quer responder ainda é manual: "quanto comprar deste SKU, de quem, e por quê?".

Responder isso exige regras de estratégia de compra (teto de estoque, folga na chegada, ritmo de compra, qual prazo de fornecedor confiar). Essas regras são do comprador, não do desenvolvedor: o desenvolvedor do projeto não domina estoque, e cada operação tem sua própria política. A política atual do atacadista existe só como documento de texto no corpus (`politicas/estoque-e-giro.md` v3), inacessível ao código.

Ao mesmo tempo, parte do cálculo não é estratégia e sim corretude: contar o que já está em trânsito, descontar o que vai ser vendido enquanto a compra não chega, nunca esconder uma violação de política. Isso tem que ser garantido pelo sistema, independente de quem configura.

## Solution

1. **Política de compra versionada** (módulo novo `politica_compra`): um conjunto fechado e tipado de parâmetros, gravado no schema `copilot`, editável via `GET/PUT /politica-compra`. Cada edição cria uma versão nova. A v1 nasce na migration com os valores da política v3 do corpus. É a fonte da verdade do cálculo (ADR-0003).
2. **Estoque em trânsito** (`inventory.em_transito`): lê do ERP o que falta chegar dos pedidos de compra abertos.
3. **Sugestão de pedido** (módulo novo `purchasing`): `sugerir_pedido(sku_code)` aplica um mecanismo fixo usando os parâmetros da política ativa e devolve uma `SugestaoPedido` com quantidade, fornecedor, memória de cálculo, alertas e a versão da política usada. Quando não há o que comprar, devolve quantidade 0 com motivo tipado.
4. **Endpoint** `GET /skus/{sku_code}/sugestao-compra`, calculado na hora, sem gravar a sugestão.

A tela de onboarding que preenche a política fica para o M7. As perguntas dela já estão em `perguntas-comprador.md`.

## User Stories

### Comprador chefe

1. Como comprador chefe, quero pedir uma sugestão de compra para um SKU pelo `sku_code` e receber quantidade, fornecedor e valor estimado, para não calcular na planilha.
2. Como comprador chefe, quero que a sugestão considere o que já está a caminho de pedidos anteriores, para não comprar duas vezes.
3. Como comprador chefe, quero que a sugestão considere o que vou vender enquanto a compra não chega, para a mercadoria chegar antes de faltar.
4. Como comprador chefe, quero ser avisado quando o estoque vai acabar antes da compra chegar, para agir com urgência (trocar fornecedor, pedir entrega parcial).
5. Como comprador chefe, quero que, quando não há o que comprar, o sistema diga isso e o motivo, em vez de dar erro.
6. Como comprador chefe, quero ver a memória de cálculo (giro, posição, lead time usado, estoque na chegada), para confiar no número ou discordar dele.
7. Como comprador chefe, quero ser avisado quando o MOQ do fornecedor obriga a passar do teto de estoque, para decidir conscientemente.
8. Como comprador chefe, quero ser avisado quando a compra de um SKU sozinha não atinge o pedido mínimo do fornecedor, para juntar com outros SKUs.
9. Como comprador chefe, quero ser avisado quando o fornecedor costuma atrasar em relação ao prazo contratado.
10. Como comprador chefe, quero ser avisado quando a compra vai chegar numa época forte, para decidir se uso o estoque extra sazonal (R2, que exige ata).
11. Como comprador chefe, quero que SKUs novos, sem histórico suficiente, não recebam sugestão automática, para decidir eu mesmo (R3).
12. Como comprador chefe, quero ver e editar a política de compra (teto, pisos, ciclo, critério de fornecedor, etc), para que as sugestões reflitam a minha operação.
13. Como comprador chefe, quero que a lista de SKUs abaixo do piso use o piso de alerta da minha política.
14. Como comprador chefe, quero saber com qual versão da política uma sugestão foi calculada, para entender por que a sugestão mudou depois que editei a política.

### Desenvolvedor

15. Como desenvolvedor, quero que a política seja um objeto tipado com campos fechados e validação, para não construir um motor de regras genérico.
16. Como desenvolvedor, quero que `purchasing` leia só dos módulos de domínio (`ficha_sku`, `inventory`, `sales`, `politica_compra`), nunca do `ERPAdapter` direto, para respeitar a ADR-0001.
17. Como desenvolvedor, quero `InMemory` para a política e para o ERP, para testar `purchasing` sem Postgres.

## Implementation Decisions

### Divisão entre mecanismo e parâmetro (ADR-0003)

**Fixo no código (corretude):** posição inclui em trânsito; consumo durante o lead time é descontado; sugestão sempre existe (quantidade 0 + motivo quando não compra); MOQ sempre respeitado; violação de teto sempre vira alerta, nunca é escondida nem zera a sugestão.

**Parâmetro da política (do comprador):** tudo que é preferência ou apetite de risco, listado abaixo.

### `PoliticaCompra` v1

| Campo | Tipo | Padrão v1 | Origem |
|---|---|---|---|
| `teto_meses` | float | 3.0 | R1 |
| `piso_alerta_dias` | int | 20 | R4 |
| `piso_reposicao_dias` | int | 30 | R4 |
| `ciclo_compra_meses` | float | 1.0 | a validar com o comprador |
| `lead_time_base` | enum `observado` / `contratado` / `maior` | `observado` | a validar com o comprador |
| `criterio_fornecedor` | enum `menor_preco` / `menor_lead_time` | `menor_preco` | a validar com o comprador |
| `sazonalidade_modo` | enum `ignorar` / `alertar` | `alertar` | a validar com o comprador |
| `meses_quentes` | list[int] (1-12) | [5, 6, 11, 12] | R2 (dia das mães, namorados, Natal) |
| `extra_sazonal_meses` | float | 2.0 | R2 |
| `dias_historico_minimo` | int | 60 | R3 |

O modo `ajustar` da sazonalidade (multiplicar o giro pelo fator sazonal) fica fora do M3. O enum só contém o que está implementado.

**Validação** (Pydantic, `PUT` responde 422 se falhar):
- `teto_meses > 0`, `ciclo_compra_meses > 0`, `extra_sazonal_meses >= 0`, `dias_historico_minimo >= 0`
- `1 <= piso_alerta_dias <= piso_reposicao_dias`
- `piso_reposicao_dias / 30 + ciclo_compra_meses <= teto_meses` (senão toda compra violaria o teto)
- `meses_quentes` sem repetição, cada valor em 1..12

**Versionamento:** tabela `copilot.politicas_compra`, append-only, uma coluna tipada por parâmetro (`meses_quentes` como `int[]`), mais `versao` (inteiro crescente, PK) e `criada_em`. A ativa é a de maior `versao`. `PUT` recebe a política completa e insere uma versão nova. Não há `UPDATE` nem `DELETE`. A migration `0002` cria a tabela e insere a v1 com os valores literais (a migration não importa código da aplicação).

### Módulo `politica_compra`

```
src/politica_compra/
├── schemas.py        ParametrosPolitica (validado), PoliticaCompra (versao, criada_em, parametros)
├── repositorio.py    Protocol PoliticaCompraRepositorio
├── postgres.py       PostgresPoliticaCompraRepositorio
├── in_memory.py      InMemoryPoliticaCompraRepositorio (nasce com a v1 padrão)
├── dependencies.py
└── tests/
```

Port:

```python
class PoliticaCompraRepositorio(Protocol):
    def ativa(self) -> PoliticaCompra: ...
    def salvar_nova_versao(self, parametros: ParametrosPolitica) -> PoliticaCompra: ...
```

Endpoints (em `src/api/politica_compra.py`, com DTOs HTTP em `src/api/schemas.py`):
- `GET /politica-compra` devolve a ativa com `versao` e `criada_em`.
- `PUT /politica-compra` recebe os parâmetros completos, valida, grava a versão nova e a devolve (201).

`GET /skus/abaixo-do-piso`: o query param `dias` passa a ser opcional. Sem ele, usa `piso_alerta_dias` da política ativa. `inventory.abaixo_do_piso(dias_piso)` não muda.

### Estoque em trânsito

Método novo no `ERPAdapter` (Postgres e InMemory):

```python
def itens_em_transito_de(self, sku_code: str) -> list[ItemEmTransito]: ...
```

`ItemEmTransito` (DTO em `src/inventory/schemas.py`): `pedido_id`, `fornecedor_id`, `status`, `quantidade_pendente` (= `quantidade - quantidade_recebida`), `data_prevista_entrega`. Considera só pedidos `aprovado`, `enviado` e `recebido_parcial`, e só itens com `quantidade_pendente > 0`. `rascunho` e `cancelado` ficam de fora.

`Inventory.em_transito(sku_code) -> EmTransito` com `total_unidades` e a lista de itens.

A cobertura do M2 (`inventory.cobertura_meses`) **não muda**: continua usando só `quantidade_disponivel`. Em trânsito entra só na posição usada pela sugestão.

### Mecanismo da sugestão

Entradas: ficha do SKU (`ficha_sku.completa`), `inventory.em_transito`, `sales.sazonalidade`, data da primeira venda (via `sales`), política ativa, relógio injetável (`now`, como em `Sales`).

**1. Motivos para quantidade 0**, checados nesta ordem:
1. `sku_novo`: a primeira venda do SKU tem menos de `dias_historico_minimo` dias. (SKU sem nenhuma venda cai em `sem_giro`.)
2. `sem_giro`: giro médio mensal igual a 0.
3. `sem_fornecedor`: nenhum fornecedor ativo com vínculo ativo.
4. `acima_do_ponto_de_reposicao`: resultado do cálculo abaixo com o fornecedor escolhido.

**2. Cálculo por fornecedor candidato** (todos em unidades; dias viram meses por `/ 30`):
- `lead_time_dias` conforme `lead_time_base`: `observado` (se nulo, usa o contratado), `contratado`, ou `maior` dos dois.
- `posicao = disponivel + em_transito`
- `estoque_na_chegada = max(0, posicao - giro * lead_time_meses)`
- `precisa_comprar = estoque_na_chegada < giro * piso_reposicao_meses`
- `qtd_necessaria = ceil(giro * (piso_reposicao_meses + ciclo_compra_meses) - estoque_na_chegada)` se `precisa_comprar`, senão 0
- `qtd = max(qtd_necessaria, moq)` se `qtd_necessaria > 0`, senão 0
- `cobertura_na_chegada_meses = (estoque_na_chegada + qtd) / giro`
- `cabe_no_teto = qtd == 0 or cobertura_na_chegada_meses <= teto_meses`

Premissa: o que está em trânsito chega antes da compra nova.

**3. Escolha do fornecedor:**
1. Ordena os candidatos por `criterio_fornecedor` (`menor_preco`: preço, depois lead time; `menor_lead_time`: lead time, depois preço).
2. Escolhe o primeiro que `cabe_no_teto`.
3. Se nenhum couber, escolhe o primeiro da ordem e adiciona o alerta `viola_teto`.
4. Se a `qtd` do escolhido for 0, a sugestão sai com quantidade 0, motivo `acima_do_ponto_de_reposicao` e sem fornecedor.

**Exemplo:** giro 100/mês, lead time observado 62 dias, 150 disponíveis, nada em trânsito, política v1. `estoque_na_chegada = max(0, 150 - 206,7) = 0`, alerta `ruptura_antes_da_chegada`. `qtd_necessaria = ceil(100 * (1 + 1) - 0) = 200`. Cobertura na chegada 2,0 meses, dentro do teto de 3.

**4. Alertas** (lista, cada um com `tipo` e `mensagem` em português):

| Tipo | Quando |
|---|---|
| `ruptura_antes_da_chegada` | `posicao < giro * lead_time_meses` do escolhido |
| `viola_teto` | nenhum candidato coube no teto (só acontece por MOQ, porque a validação da política garante que piso + ciclo cabe) |
| `abaixo_pedido_minimo` | `qtd * preco_unitario < pedido_minimo_reais * 100`. Atenção: o preço está em centavos e o pedido mínimo em reais inteiros |
| `lead_time_observado_acima_do_contratado` | o escolhido tem observado maior que contratado, independente de `lead_time_base` |
| `periodo_sazonal` | `sazonalidade_modo = alertar` e algum mês do calendário entre a chegada (`now + lead_time_dias`) e a chegada + `ciclo_compra_meses` está em `meses_quentes`. A mensagem cita a R2: até `extra_sazonal_meses` a mais, com registro em ata |

Alertas só são calculados quando `quantidade > 0`.

### `SugestaoPedido` (DTO de domínio em `src/purchasing/schemas.py`)

- `sku_code`
- `quantidade: int`
- `motivo: MotivoSemCompra | None` (preenchido só quando `quantidade == 0`)
- `fornecedor: FornecedorParaSKU | None`
- `valor_estimado_centavos: int` (`quantidade * preco_unitario`, 0 sem compra)
- `calculo: MemoriaCalculo | None` (ausente para `sku_novo`, `sem_giro` e `sem_fornecedor`): `giro_mensal`, `disponivel`, `em_transito`, `posicao`, `lead_time_dias`, `lead_time_origem` (`observado` / `contratado`), `estoque_na_chegada`, `qtd_necessaria`, `cobertura_na_chegada_meses`
- `alertas: list[Alerta]`
- `politica_versao: int`

### Módulo `purchasing`

```
src/purchasing/
├── schemas.py
├── service.py        Purchasing.sugerir_pedido(sku_code) -> SugestaoPedido | None
├── dependencies.py
└── tests/
```

Construtor recebe `FichaSKU`, `Inventory`, `Sales`, `PoliticaCompraRepositorio` e `now` opcional. Retorna `None` para SKU inexistente. Propaga `SKUSemEstoque` como o `ficha_sku`.

Os outros métodos de `module-interfaces.md` (`validar_contra_politica`, `submeter_pedido`, `registrar_decisao_humana`, `list_sugestoes`) ficam fora.

### Endpoint

`GET /skus/{sku_code}/sugestao-compra` projeta `SugestaoPedido` num DTO HTTP. 404 para SKU inexistente, 500 para `SKUSemEstoque` (mesmo tratamento do `/analise`).

## Testing Decisions

Testar comportamento pela interface pública, com os padrões do spec 01 e 02: unitários com `InMemoryERPAdapter` e `InMemoryPoliticaCompraRepositorio`, integração dos adapters Postgres contra banco real, HTTP com `TestClient` e `dependency_overrides`, smoke contra Postgres com seed.

- **`politica_compra`**: `ativa` devolve a v1 padrão; `salvar_nova_versao` incrementa a versão e a nova vira ativa; versões antigas continuam gravadas; cada regra de validação rejeita um caso inválido. Integração do repositório Postgres. HTTP: `GET`, `PUT` feliz, `PUT` inválido (422).
- **`inventory.em_transito`**: soma só os status que contam; `recebido_parcial` conta só o pendente; `rascunho` e `cancelado` não contam; SKU sem pedidos devolve 0. Integração Postgres do método novo do adapter.
- **`purchasing`**: um teste por motivo; o exemplo desta spec reproduzido número a número; em trânsito reduzindo a quantidade; cada `lead_time_base`; cada `criterio_fornecedor`; MOQ empurrando pro fornecedor seguinte; `viola_teto` quando nenhum cabe; cada alerta aparecendo e não aparecendo; mudar a política muda a sugestão e a `politica_versao`.
- **HTTP**: `/sugestao-compra` feliz, 404, e quantidade 0 com motivo. `/abaixo-do-piso` sem `dias` usa a política.
- **Smoke**: os endpoints novos entram em `tests/smoke/test_endpoints.py`.

## Out of Scope

- Tela de onboarding (M7). As perguntas estão em `perguntas-comprador.md`.
- Gravar sugestões, aprovar, submeter pedido ao ERP (M7).
- Sugestão em lote (`/sugestoes-compra`) e agrupamento de SKUs por fornecedor.
- Faixa de aprovação (depende do valor do pedido inteiro, com impostos e frete, e de exceções como fornecedor novo). Fica pro M7.
- Modo `ajustar` da sazonalidade e `sales.previsao_venda`.
- Janela do giro configurável (continua 6 meses fixos).
- Endpoint de histórico de versões da política.
- Multi-tenant (um atacadista só).
- Detectar divergência entre a política gravada e o documento do corpus.
- Renomear `preco_unitario_reais` (que guarda centavos) nos DTOs existentes.

## Further Notes

- Os padrões marcados "a validar com o comprador" são chutes do dev. As respostas de `perguntas-comprador.md` viram um `PUT /politica-compra`, sem mudança de código.
- O seed tem pedidos `enviado`, `aprovado` e `recebido_parcial`, então o caso em trânsito aparece nos dados reais do smoke.
- Ordem dos tickets em `issues/`: 01 e 02 em paralelo, 03 depende dos dois, 04 e 05 dependem do 03, 06 fecha.
