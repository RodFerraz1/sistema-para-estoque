# 08: Tela de Estoque

**What to build:** o comprador chefe tem uma tela com todos os SKUs ativos, não só os do painel: código, produto, cor, tamanho, categoria, disponível, em trânsito, venda média diária e cobertura em dias. Ela é paginada, ordena por cobertura, venda diária ou nome, filtra por busca, categoria e situação (em ruptura, sem venda, com compra em trânsito) e cada linha abre a tela do SKU.

**Blocked by:** 03, 07

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Escala: leitura em lote e filtros")

- [ ] `GET /estoque?busca=&categoria=&situacao=&ordem=&pagina=&por_pagina=` (no máximo 100 por página), com itens e total, lido do retrato em lote. Só o papel comprador.
- [ ] `estoque.html` no visual atual, com a mesma barra de busca e filtros do painel, paginação e o link "Estoque" na navegação do comprador.
- [ ] Testes HTTP: cada situação, cada ordem, paginação (última página, página fora do total) e 403 para os outros papéis.
- [ ] Verificado no navegador. Typecheck e suíte completa verdes.
