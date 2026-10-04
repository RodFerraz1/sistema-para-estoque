# 05: Seed com vendas diárias e os cenários da reunião

**What to build:** o ERP fake passa a contar a história do comprador. O seed gera dados até a data em que roda, com vendas diárias nos últimos 90 dias (domingos fechados), e tem cenários fixos: o tapete marrom que vendia 10 por dia e parou com estoque, um SKU em ruptura sem pedido, um pedido enviado com data prevista vencida há 10 dias contendo um SKU em ruptura, e um SKU que parou de vender sem estoque. Um modo gera milhares de SKUs para medir escala.

**Blocked by:** 01

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Seed e dados de demonstração")

- [x] `NOW` do seed é o dia em que ele roda. Mesmo dia, mesmo banco: o seed continua reprodutível e idempotente.
- [x] Vendas diárias nos últimos 90 dias, uma linha por SKU e dia aberto, sem venda aos domingos. Antes disso continua o padrão mensal. A giro do mês corrente não cai mais por falta de dado.
- [x] Produto "Tapete Banheiro", categoria `banho`, com a cor marrom, e os quatro cenários com códigos de SKU estáveis, documentados no topo do seed.
- [x] O Tapete Banheiro tem 5 cores com participação nas vendas bem diferente (marrom perto de 45%, branco perto de 8%), para o mix de gôndola.
- [x] `--skus N` gera N SKUs sintéticos a mais.
- [x] O teste de smoke do seed confere os cenários (o tapete com estoque e venda recente baixa, o pedido com data vencida etc.).
- [x] Painel, tela do SKU e chat continuam funcionando com o seed novo (verificado no navegador).

## Comments

**2026-10-03 (agente):** `scripts/seed.py` reescrito: `NOW` é a meia-noite UTC do dia em que roda; padrão mensal até 90 dias atrás e, daí até ontem, no máximo uma venda por SKU e dia aberto (domingo fechado; dia com venda zero não grava linha, para não inflar a giro dos SKUs de venda baixa); hoje não tem venda. Cada SKU tem a própria semente (`SEED:historico:<sku>`), então `--skus N` não muda os 85 SKUs padrão. A venda diária varia pouco em volta da média (0,8 a 1,2), para nenhum SKU fora dos cenários parecer ter parado de vender (o smoke confere com a Poisson da spec). Produto "Tapete Banheiro" (`banho`, migration `0016_categoria_banho` na constraint de categoria) com sigla `TAP`: com `TB-` a ordenação do Postgres (que ignora o hífen) discordava da do Python no `test_listar_skus`. Cenários como constantes no topo do seed (`TAPETE_MARROM`, `TAPETE_BRANCO`, `RUPTURA_SEM_PEDIDO`, `RUPTURA_COM_PEDIDO_ATRASADO`, `QUEDA_SEM_ESTOQUE`), em `CENARIOS`. Decisões: o tapete marrom vendeu 5 e depois 0 nos dois últimos dias abertos (anteontem 5, ontem 0), que é a janela "5 + 0" da spec na ordem da história (10, 5, 0); o texto "ontem 5" da spec punha o 0 antes do 5. `RUPTURA_SEM_PEDIDO` é o `JDCP-BRAN-CASAL-01` com a Katrina forçada como mais barata (MOQ 24), e o smoke de sinais passou a usar a constante. O pedido atrasado é da Katrina, com o `TBC-BEGE-70140-02` e mais dois SKUs dela. Os pedidos em trânsito aleatórios agora são recentes e estão no prazo (antes todos os `enviado` e `recebido_parcial` já estavam vencidos), e não levam SKU de cenário: o do cenário é o único atrasado. Com o seed novo o painel tem 10 SKUs em ruptura (o `PM-AMAR-3040-01` zerado primeiro). `--skus 5000` leva uns 70 s (1,25 milhão de vendas), em lotes de 5.000 linhas. Para os próximos: setores, gôndola e usuários de cada papel não entraram (tickets 14 e outros); o reset do README apagou os avisos e a decisão do dev que o ticket 01 deixou. Suíte com 900 testes verde (smoke incluído); pyright com os mesmos 79 erros por arquivo.
