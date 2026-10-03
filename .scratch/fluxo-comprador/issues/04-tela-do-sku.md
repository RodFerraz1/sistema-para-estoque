# 04: Tela do SKU

**What to build:** o comprador chefe clica num SKU do painel e cai numa tela com tudo o que precisa para decidir: situação do estoque, vendas mês a mês, sugestão de pedido com memória de cálculo e alertas, sinais do corpus e referências de preço para a negociação com o representante (histórico de preço pago, preço atual por fornecedor e substitutos).

**Blocked by:** 02

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "`purchasing`", "`erp_adapter`", "API" e "UI")

- [x] O ERP fake ganha `itens_de_pedido_de(sku_code)` (em memória e Postgres): itens de pedido de compra do SKU com data, fornecedor e status do pedido.
- [x] `purchasing.referencias_de_preco(sku_code)` devolve:
  - o histórico de preço, do mais recente para o mais antigo e sem pedidos cancelados;
  - o preço atual de cada fornecedor;
  - até 10 substitutos (SKUs ativos de outro produto, mesma categoria e tamanho), ordenados pelo menor preço atual, com o fornecedor desse preço.
- [x] `GET /skus/{sku}/precos` responde 200, e 404 para SKU inexistente.
- [x] `sku.html?sku=` mostra código, produto, cor e tamanho. Os blocos aparecem em paralelo a partir das rotas existentes:
  - situação: disponível, em trânsito, posição, giro e cobertura;
  - vendas dos últimos 12 meses;
  - sugestão de pedido, com o motivo quando a quantidade for zero;
  - preços.
- [x] Os sinais do corpus carregam por último sem bloquear a tela. Com o Jev fora do ar, o bloco mostra "indisponível".
- [x] SKU inexistente no link mostra mensagem clara.
- [x] As linhas do painel abrem a tela do SKU.
- [x] Testes HTTP cobrem o histórico (incluindo que ignora cancelado), os substitutos (categoria, tamanho, ordem e limite) e o 404. O teste de UI cobre `sku.html`.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões:

- **ERP**: `itens_de_pedido_de(sku_code)` na porta e nas duas implementações, devolvendo `ItemDePedido` (pedido, data, fornecedor com nome, status, quantidade, preço pago em centavos), do pedido mais recente para o mais antigo, de todos os status. O DTO e `StatusPedidoCompra` ficam em `erp_adapter/schemas.py` (pedido de compra não tem módulo de leitura, e o `erp_adapter` não importa de `purchasing`). `PedidoCompra` em memória ganhou `criado_em`.
- **`purchasing.referencias_de_preco`**: o `Purchasing` passou a receber o `Catalog` (para o SKU, os SKUs ativos e os fornecedores), em vez de ler o `ERPAdapter` direto, que segue só para pedidos. Histórico sem cancelados (rascunho fica, como a spec pede). Substitutos: outro `produto_id`, mesma categoria e tamanho, ativos, com fornecedor ativo, pelo menor preço (código desempata), no máximo 10.
- **Em trânsito na tela**: a análise não tinha em trânsito, cor nem tamanho. `Ficha` ganhou `em_transito` (o `ficha_sku` já depende do `inventory`) e `AnaliseSKUResponse` ganhou `cor`, `tamanho` e `em_transito_unidades`. Assim a situação aparece mesmo sem memória de cálculo (SKU novo, sem giro, sem fornecedor). O contexto do redator do chat não mudou.
- **UI**: `sku.html` + `sku.js`. Situação, sugestão (com motivo por extenso quando é zero, alertas e memória de cálculo recolhida), sinais, preços (o que já pagamos, preço atual por fornecedor, substitutos com link para a tela deles) e vendas dos 12 meses em tabela com barra proporcional (mês sem venda ganha a nota de possível ruptura). Os blocos pedem as rotas em paralelo, e os sinais são pedidos depois que os outros terminam; 503 vira "Sinais indisponíveis: o Jev está fora do ar". Link sem `?sku=` ou com SKU inexistente esconde os blocos e mostra a mensagem. No painel, o nome do produto é link e a linha inteira é clicável.
- **Ajustes de UI achados no navegador**: `[hidden]` agora vence `display` (a caixa do produto escolhido aparecia vazia na página de aviso), e a busca do aviso mostra o código do SKU, porque o seed tem dois SKUs "Toalha Banho Conforto, bege, 70x140" de produtos diferentes.
- **Verificação manual** (Chrome, banco local com seed e Jev real): painel com 9 SKUs; tela do `JDCP-ROSA-SOLTEIRO-10` com todos os blocos e o sinal de encalhe do corpus; SKU inexistente com mensagem; aviso enviado pela página (busca "jogo americano bege", vendendo muito, comentário, nome lembrado), que apareceu no painel com 1 aviso aberto. O aviso de teste foi apagado depois.
- **Seed**: o histórico de preço é ralo (15 pedidos no seed inteiro, ao preço atual). O SKU acima não tem pedido. Fica para o ticket 07 decidir se a demo precisa de mais dados.
- `uv run pytest -q` com Postgres: 732 passando. Pyright sem erro novo.
