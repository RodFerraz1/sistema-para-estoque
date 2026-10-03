# Interfaces públicas dos módulos

Cada módulo do monolito modular expõe uma interface Python explícita. Módulos NÃO acessam banco uns dos outros nem chamam funções internas de outro módulo. Só interfaces.

## Regra de ouro

Toda função pública recebe e retorna **DTOs do próprio módulo**, não SQLAlchemy models nem dicts crus. DTOs vivem em `<modulo>/schemas.py` (Pydantic). Isso é o que vai permitir quebrar em microserviço no futuro - as interfaces já parecem chamadas RPC.

## Dependência entre módulos

```
           api
            │
            ▼
           ai ──────► painel
            │           │
            ▼           │
        purchasing ◄────┘
         │      │   └────────────┐
         ▼      ▼                │ histórico de preço
      sales  inventory           │
         │      │                │
         └──┬───┘                │
            ▼                    │
         catalog                 │
            │                    │
            ▼                    │
       erp_adapter ◄─────────────┘
            │
            ▼
      (ERP fake DB, só leitura)
```

- `ai` orquestra e chama outros módulos como tools do LLM, **respeitando divisão por risco** (ver seção abaixo).
- `painel` calcula o painel de alertas na hora e guarda os avisos da equipe de vendas e as decisões de compra (append-only, em `copilot.avisos` e `copilot.decisoes_compra`). Depende de `purchasing` (sugestão de cada SKU ativo), `catalog`, `inventory` e `politica_compra` (motivos de alerta da política ativa). Não chama o Jev. O `ai` depende dele para a intenção `alertas_e_avisos`. Ver ADR-0005.
- `purchasing` é o único que sabe compor sugestões formais de compra - combina dados dos outros de forma determinística.
- `purchasing -> erp_adapter`: só para o histórico de preço pago (`itens_de_pedido_de`, nas referências de preço da tela do SKU). Pedido de compra não tem módulo de leitura próprio, e criar um só para repassar uma chamada seria um módulo raso. O status do pedido (`StatusPedidoCompra`) fica em `erp_adapter/schemas.py`, então a aresta tem um sentido só e não há ciclo. O Copilot não escreve no ERP (ADR-0005).
- `catalog`, `inventory`, `sales` são "leitores" do ERP com lógica de domínio própria (não são só query wrappers).
- `erp_adapter` é a única camada que fala com o banco do ERP fake. Importa os DTOs de domínio de `catalog`, `inventory` e `sales` para devolvê-los prontos, mas nunca de `purchasing` nem de módulos acima.

Sem ciclos. Se surgir vontade de fazer `catalog` chamar `sales`, é sinal de que a fronteira está errada.

## Divisão de tools por nível de risco

> Desde a ADR-0002 quem escolhe a tool é o Jev (pergunta tipada com confiança) e quem chama é o código do `ai`. O LLM só redige a resposta e não tem tools. Onde abaixo se lê "LLM chama", leia "o `ai` chama após decisão do Jev". A divisão por risco não muda.

O `ai` só pode chamar diretamente **tools de leitura**. Tools que compõem decisão passam por `purchasing` (determinístico), e a decisão de compra é sempre do comprador chefe.

**Tools de leitura (LLM chama direto)**:
- `catalog.get_sku`, `catalog.list_fornecedores_para_sku`, `catalog.skus_similares`
- `inventory.estoque_atual`, `inventory.cobertura_meses`, `inventory.historico_movimentacoes`, `inventory.projetar_estoque`
- `sales.giro_medio_mensal`, `sales.historico_vendas`, `sales.sazonalidade`, `sales.previsao_venda`
- `ai.buscar_contexto` (RAG)

Se o LLM alucinar em leitura, o pior é resposta ruim - nada muda no mundo.

**Tools de composição de decisão (LLM chama via `purchasing`)**:
- `purchasing.sugerir_pedido`: LLM pode chamar. Retorna sugestão estruturada e determinística. `purchasing` internamente consulta os leitores e aplica política.
- `purchasing.validar_contra_politica`: LLM pode chamar.

**Ações irreversíveis**: nenhuma. Desde a ADR-0005 o Copilot termina na decisão de compra e o ERP é só leitura: o comprador chefe negocia com o representante e lança o pedido no ERP real.

**Escritas humanas (LLM NÃO chama)**:
- `painel.registrar_decisao`: decisão de compra do comprador chefe, só via `POST /skus/{sku_code}/decisoes` (tela do SKU). Fica no Copilot e não muda o ERP.
- `painel.registrar_aviso`: aviso da equipe de vendas, só via `POST /avisos` (página de aviso).

Essa divisão é o que impede alucinação de virar prejuízo real.

## Interfaces propostas

### `erp_adapter`

Port abstrato. Mesma interface serve pro ERP fake e um ERP real futuro.

```python
class ERPAdapter(Protocol):
    def get_sku_raw(self, sku_id: UUID) -> SKURaw: ...
    def list_skus_raw(self, filtros: FiltrosSKU) -> list[SKURaw]: ...
    def get_fornecedor_raw(self, fornecedor_id: UUID) -> FornecedorRaw: ...
    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorSKURaw]: ...
    def get_estoque_atual(self, sku_id: UUID) -> int: ...
    def list_movimentacoes(self, sku_id: UUID, desde: date) -> list[MovimentacaoRaw]: ...
    def list_vendas(self, sku_id: UUID, desde: date) -> list[VendaRaw]: ...
    def get_pedido_compra(self, pedido_id: UUID) -> PedidoCompraRaw: ...
    def list_pedidos_compra(self, filtros: FiltrosPedido) -> list[PedidoCompraRaw]: ...
```

Retornam tipos "Raw" - crus, refletindo o schema do ERP. Módulos de cima transformam em conceitos de domínio.

### `catalog`

Sabe sobre SKU, produto, fornecedor. Nao sabe sobre estoque, venda ou pedido.

```python
class Catalog:
    def get_sku(self, sku_id: UUID) -> SKU: ...
    def buscar_sku_por_codigo(self, sku_code: str) -> SKU | None: ...
    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorPara(SKU)]: ...
    def melhor_fornecedor_por_preco(self, sku_id: UUID) -> FornecedorPara(SKU) | None: ...
    def skus_similares(self, sku_id: UUID) -> list[SKU]:  # mesmo produto, cor/tamanho diferente
        ...
```

`FornecedorPara(SKU)` = fornecedor + preço + moq + lead time observado. Estruturado, não raw.

### `inventory`

Sabe sobre estoque atual, movimentação, cobertura.

```python
class Inventory:
    def estoque_atual(self, sku_id: UUID) -> Estoque: ...  # qtd disponível + reservada
    def cobertura_meses(self, sku_id: UUID) -> float: ...  # estoque / giro. usa Sales pra giro
    def abaixo_do_piso(self, dias_piso: int = 20) -> list[UUID]: ...  # SKUs em alerta
    def historico_movimentacoes(self, sku_id: UUID, dias: int = 90) -> list[Movimentacao]: ...
    def projetar_estoque(self, sku_id: UUID, dias_frente: int) -> ProjecaoEstoque: ...
```

_Nota_: `cobertura_meses` precisa de giro. Injeta `Sales` no construtor. Isso é dependência intra-módulo, feita explícita.

### `sales`

Sabe sobre venda, giro, sazonalidade, previsão.

```python
class Sales:
    def giro_medio_mensal(self, sku_id: UUID, meses: int = 6) -> float: ...
    def historico_vendas(self, sku_id: UUID, meses: int = 12) -> list[VendaMensal]: ...
    def sazonalidade(self, sku_id: UUID) -> Sazonalidade: ...  # multiplicadores por mês
    def previsao_venda(self, sku_id: UUID, horizonte_meses: int) -> Previsao: ...
```

Previsão pode ser burra no MVP (ex: giro médio × sazonalidade), depois evoluir pra modelo estatístico.

### `purchasing`

Orquestra sugestão de compra. Único que sabe compor a decisão.

```python
class Purchasing:
    def sugerir_pedido(self, sku_code: str) -> SugestaoPedido | None: ...
    def politica_da(self, sugestao: SugestaoPedido) -> PoliticaCompra: ...  # versão com que foi calculada
    def referencias_de_preco(self, sku_code: str) -> ReferenciasDePreco | None: ...  # preço pago, preço atual, substitutos
```

`SugestaoPedido` é rica: SKU, quantidade sugerida, fornecedor sugerido, memória de cálculo, alertas de política (violação de teto de estoque, etc) e a versão da política usada. A decisão de compra fica no `painel`.

### `painel`

Painel de alertas do comprador chefe, avisos da equipe de vendas e decisões de compra (ADR-0005). Avisos e decisões ficam atrás dos ports `AvisosRepositorio` e `DecisoesRepositorio`.

```python
class Painel:
    def painel(self) -> PainelDeAlertas: ...  # calculado na hora: alertas e decididos
    def registrar_aviso(self, sku_code: str, tipo: TipoAviso, avisado_por: str, comentario: str | None = None) -> Aviso: ...
    def registrar_decisao(self, sku_code: str, tipo: TipoDecisao, decidido_por: str, quantidade: int | None = None, motivo: str | None = None, comentario: str | None = None) -> DecisaoCompra: ...
    def avisos_abertos(self, sku_code: str) -> list[Aviso]: ...
    def decisoes(self, sku_code: str) -> list[DecisaoCompra]: ...
```

Depende de `catalog`, `inventory`, `politica_compra` e `purchasing`. Aviso aberto e decisão vigente saem das datas: nada é atualizado.

### `ai`

RAG, roteamento de decisões (Jev), redação da resposta (LLM). Ver ADR-0002.

```python
class AICopilot:
    async def responder(self, pergunta: str, sessao_id: UUID) -> RespostaCopilot: ...
    async def sugerir_para_sku(self, sku_id: UUID) -> SugestaoComExplicacao: ...
    def indexar_documento(self, doc: DocumentoRAG) -> None: ...
    def buscar_contexto(self, query: str, k: int = 5) -> list[TrechoRelevante]: ...
```

Internamente `ai` pergunta ao Jev qual é a intenção e qual tool usar, chama `Purchasing`, `Catalog`, `Inventory` e `Sales` no código e entrega os dados ao LLM só para redigir. Jev e LLM ficam cada um atrás do seu port.

## Separação de bancos

O ERP fake e o Copilot devem viver em bancos separados **logicamente**, mesmo que rodem no mesmo Postgres:

- `erp_db` (ou schema `erp`): produtos, skus, fornecedores, estoque, vendas, pedidos_compra.
- `copilot_db` (ou schema `copilot`): política de compra, avisos, decisões de compra, embeddings dos documentos, registro de decisão do chat.

Motivo: o ERP fake simula um sistema externo. O Copilot não escreve nessas tabelas (ADR-0005). Ter bancos separados torna essa separação um *guard rail* que o schema aplica sozinho.

Duas opções:

- **(a) Um Postgres, dois schemas** (`erp` e `copilot`). Mais simples pra desenvolvimento local, ainda deixa claro a separação. Migração pra bancos físicos separados vira trivial.
- **(b) Dois containers Postgres separados** desde o dia 1. Mais realista, ensina você a lidar com "meu app fala com dois bancos". Mais overhead no docker-compose.

Recomendação: **(a) por enquanto, com plano explícito de migrar pra (b) quando o `ai` virar o primeiro microserviço** (que provavelmente vai querer conexão só com `copilot_db` e chamar API do `erp_adapter` já como serviço).
