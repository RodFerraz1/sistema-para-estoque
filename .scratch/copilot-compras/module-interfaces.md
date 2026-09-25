# Interfaces públicas dos módulos

Cada módulo do monolito modular expõe uma interface Python explícita. Módulos NÃO acessam banco uns dos outros nem chamam funções internas de outro módulo. Só interfaces.

## Regra de ouro

Toda função pública recebe e retorna **DTOs do próprio módulo**, não SQLAlchemy models nem dicts crus. DTOs vivem em `<modulo>/schemas.py` (Pydantic). Isso é o que vai permitir quebrar em microserviço no futuro - as interfaces já parecem chamadas RPC.

## Dependência entre módulos

```
       ai
        │ depende de
        ▼
  purchasing ─────┐
        │         │
        ▼         ▼
  sales    inventory
        │         │
        └────┬────┘
             ▼
         catalog
             │
             ▼
        erp_adapter
             │
             ▼
      (ERP fake DB)
```

- `ai` orquestra e chama outros módulos como tools do LLM, **respeitando divisão por risco** (ver seção abaixo).
- `purchasing` é o único que sabe compor sugestões formais de compra - combina dados dos outros de forma determinística.
- `catalog`, `inventory`, `sales` são "leitores" do ERP com lógica de domínio própria (não são só query wrappers).
- `erp_adapter` é a única camada que fala com o banco do ERP fake.

Sem ciclos. Se surgir vontade de fazer `catalog` chamar `sales`, é sinal de que a fronteira está errada.

## Divisão de tools por nível de risco

> Desde a ADR-0002 quem escolhe a tool é o Jev (pergunta tipada com confiança) e quem chama é o código do `ai`. O LLM só redige a resposta e não tem tools. Onde abaixo se lê "LLM chama", leia "o `ai` chama após decisão do Jev". A divisão por risco não muda.

O `ai` só pode chamar diretamente **tools de leitura**. Tools que geram decisão ou escrita passam por `purchasing` (determinístico) e por aprovação humana.

**Tools de leitura (LLM chama direto)**:
- `catalog.get_sku`, `catalog.list_fornecedores_para_sku`, `catalog.skus_similares`
- `inventory.estoque_atual`, `inventory.cobertura_meses`, `inventory.historico_movimentacoes`, `inventory.projetar_estoque`
- `sales.giro_medio_mensal`, `sales.historico_vendas`, `sales.sazonalidade`, `sales.previsao_venda`
- `ai.buscar_contexto` (RAG)

Se o LLM alucinar em leitura, o pior é resposta ruim - nada muda no mundo.

**Tools de composição de decisão (LLM chama via `purchasing`)**:
- `purchasing.sugerir_pedido`: LLM pode chamar. Retorna sugestão estruturada e determinística. `purchasing` internamente consulta os leitores e aplica política.
- `purchasing.validar_contra_politica`: LLM pode chamar.

**Ações irreversíveis (LLM NÃO chama - humano aprova fora do fluxo LLM)**:
- `purchasing.submeter_pedido`: cria pedido no ERP. Só é acionado por endpoint HTTP que exige aprovação humana explícita.
- `purchasing.registrar_decisao_humana`: só via UI de aprovação.

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
    def criar_pedido_compra(self, dados: NovoPedidoCompraRaw) -> UUID: ...
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
    def sugerir_pedido(self, sku_id: UUID, contexto: ContextoCompra) -> SugestaoPedido: ...
    def validar_contra_politica(self, sugestao: SugestaoPedido) -> ResultadoValidacao: ...
    def registrar_decisao_humana(self, sugestao_id: UUID, decisao: DecisaoHumana) -> None: ...
    def submeter_pedido(self, sugestao_id: UUID) -> UUID:  # cria pedido de compra no ERP
        ...
    def list_sugestoes(self, filtros: FiltrosSugestao) -> list[SugestaoPedido]: ...
```

`SugestaoPedido` é rica: SKU, quantidade sugerida, fornecedor sugerido, justificativa em texto, alertas de política (violação de teto de estoque, etc), cobertura projetada pós-compra.

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
- `copilot_db` (ou schema `copilot`): sugestões geradas, aprovações humanas, embeddings dos documentos, histórico de conversas.

Motivo: o ERP fake simula um sistema externo. O Copilot não deveria escrever nessas tabelas exceto via `erp_adapter.criar_pedido_compra()` (que representa uma chamada de API externa). Ter bancos separados torna essa separação um *guard rail* que o schema aplica sozinho.

Duas opções:

- **(a) Um Postgres, dois schemas** (`erp` e `copilot`). Mais simples pra desenvolvimento local, ainda deixa claro a separação. Migração pra bancos físicos separados vira trivial.
- **(b) Dois containers Postgres separados** desde o dia 1. Mais realista, ensina você a lidar com "meu app fala com dois bancos". Mais overhead no docker-compose.

Recomendação: **(a) por enquanto, com plano explícito de migrar pra (b) quando o `ai` virar o primeiro microserviço** (que provavelmente vai querer conexão só com `copilot_db` e chamar API do `erp_adapter` já como serviço).
