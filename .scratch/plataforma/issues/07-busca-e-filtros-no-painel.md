# 07: Busca e filtros no painel

**What to build:** o comprador chefe acha qualquer SKU no painel enquanto digita (código, nome, cor, tamanho, sem acento nem maiúscula) e filtra por categoria, por motivo e por fornecedor. Cada grupo mostra quantos SKUs tem com o filtro aplicado, e os filtros ficam na URL para mandar o link.

**Blocked by:** 06

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Escala: leitura em lote e filtros")

- [ ] `GET /painel?busca=&categoria=&motivo=&fornecedor=`, com a regra de busca do `catalog.buscar_skus` e as contagens por grupo.
- [ ] `GET /categorias` com as categorias com SKU ativo.
- [ ] Barra de busca e filtros no topo do painel, com debounce, os filtros na query string e um "limpar filtros". Mensagem própria para "nenhum SKU com esses filtros", diferente de "nada pedindo atenção".
- [ ] Testes HTTP para cada filtro, para a combinação deles e para as contagens. O teste de UI cobre as rotas novas.
- [ ] Verificado no navegador, no desktop e no celular. Typecheck e suíte completa verdes.
