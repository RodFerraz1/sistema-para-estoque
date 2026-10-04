# 08: Tela de Estoque

**What to build:** o comprador chefe tem uma tela com todos os SKUs ativos, não só os do painel: código, produto, cor, tamanho, categoria, disponível, em trânsito, venda média diária e cobertura em dias. Ela é paginada, ordena por cobertura, venda diária ou nome, filtra por busca, categoria e situação (em ruptura, sem venda, com compra em trânsito) e cada linha abre a tela do SKU.

**Blocked by:** 03, 07

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Escala: leitura em lote e filtros")

- [x] `GET /estoque?busca=&categoria=&situacao=&ordem=&pagina=&por_pagina=` (no máximo 100 por página), com itens e total, lido do retrato em lote. Só o papel comprador.
- [x] `estoque.html` no visual atual, com a mesma barra de busca e filtros do painel, paginação e o link "Estoque" na navegação do comprador.
- [x] Testes HTTP: cada situação, cada ordem, paginação (última página, página fora do total) e 403 para os outros papéis.
- [x] Verificado no navegador. Typecheck e suíte completa verdes.

## Comments

**2026-10-04 (agente):** `GET /estoque?busca=&categoria=&situacao=&ordem=&pagina=&por_pagina=` em `src/api/painel.py` (só comprador), servido por `Painel.estoque(filtro, ordem, pagina, por_pagina)` sobre o mesmo `FichaSKU.retrato()` do painel (sem `sugerir_pedidos`, que o Estoque não usa). Schemas `FiltroEstoque`, `ItemEstoque`, `PaginaDeEstoque`, `SituacaoEstoque`, `OrdemEstoque` e `POR_PAGINA_MAXIMO` em `painel.schemas`; resposta com `itens` (código, produto, cor, tamanho, categoria, disponível, em trânsito, `venda_media_diaria`, `cobertura_dias`, `em_ruptura`), `total`, `pagina` e `por_pagina`. Decisões: o Estoque mora no módulo `painel` porque a regra de ruptura já estava lá (saiu como `_em_ruptura`, usada também pelo `_motivos`); "em ruptura" é a cobertura abaixo do piso de alerta da política ativa, mesmo com o motivo desligado na política; `sem_venda` é sem giro; `com_transito` é em trânsito maior que zero. Ordens: `cobertura` crescente com os sem giro no fim, `venda_diaria` decrescente e `nome` (produto, cor e tamanho sem acento, `catalog.ordem_por_nome`, que o `buscar_skus` passou a usar), sempre com o código para desempatar. Padrão de 50 por página, `por_pagina` de 1 a 100 e `pagina` a partir de 1 (fora disso 422); página depois da última vem vazia com o total. SKU sem linha de estoque no ERP fica fora (no painel ele vai para `skus_com_erro`). O teste de consultas em escala (`test_painel_em_escala.py`) agora roda para `/painel` e `/estoque`. Com `--skus 5000` (5.085 SKUs), `/estoque` leva cerca de 0,8 s. UI: `estoque.html`/`estoque.js` com chat lateral como as outras telas do comprador, "Estoque" no menu logo depois do Painel, tabela que vira cartões no celular, contagem "101 a 150 de 5.085 SKUs", "Ordenar por" fora da barra de filtros e paginação Anterior/Próxima. A barra de filtros saiu do `painel.js` para `barraDeFiltros(formulario, aoMudar)` em `comum.js` (debounce, "Limpar filtros" com a classe `limpar-filtros`, opções com o valor da URL), mais `guardarNaUrl(parametros)`; o painel e o Estoque usam as duas. A tela do SKU aberta a partir do Estoque troca o "← Painel" por "← Estoque" e volta com os mesmos filtros. Banco local voltou ao seed padrão. Suíte com 973 testes verde; pyright com os mesmos 79 erros por arquivo.
