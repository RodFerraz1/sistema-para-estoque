# 15: Mix de gôndola

**What to build:** o repositor abre um produto (pelo card de um SKU no painel ou pela aba "Montar gôndola"), informa quantas peças cabem na gôndola e vê quantas de cada cor e tamanho colocar, pela participação de cada SKU nas vendas: 10 marrons e 2 brancos, e não 5 de cada. Toda cor com estoque ganha ao menos uma peça, nada passa do disponível e o Copilot lembra a capacidade do produto. O comprador chefe vê a mesma participação nas vendas na tela do SKU, para comprar a grade na proporção do que vende.

**Blocked by:** 11

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Mix de gôndola")

- [x] Parâmetro `dias_mix_gondola` (padrão 90) na política, com migration. Tabela `capacidades_gondola` com `usuario_id`.
- [x] Cálculo do mix no módulo `reposicao`, com o algoritmo da spec (uma peça por elegível, maiores restos, limite do disponível com redistribuição, desempate pelo código, divisão igual sem venda).
- [x] `GET /reposicao/produtos?busca=`, `GET /reposicao/produtos/{produto_id}/mix?capacidade=` e `PUT /reposicao/produtos/{produto_id}/capacidade`.
- [x] `gondola.html` mobile first, aba "Montar gôndola" no painel do repositor e link "Montar a gôndola deste produto" nos cards.
- [x] Participação nas vendas do SKU e das outras cores e tamanhos do produto na tela do SKU do comprador.
- [x] Testes HTTP: os cenários "Mix de gôndola" da spec e as permissões. Contrato do repositório de capacidades em memória e no Postgres.
- [x] Verificado no navegador, no celular, com o tapete do seed. Typecheck e suíte completa verdes.

## Comments

**2026-10-04 (agente):** tudo no módulo `reposicao`, sem Jev. Migration `0023_mix_de_gondola`: `dias_mix_gondola` (padrão 90) em todas as versões da política e `copilot.capacidades_gondola` (PK `produto_id`, `capacidade > 0`, `usuario_id`, `atualizado_em`; upsert, vale a última). `CapacidadesGondolaRepositorio` (`gravar`, `do_produto`, `todas`) com contrato em memória e Postgres. Conta pura `dividir_a_gondola(capacidade, vendido, disponivel)` com o algoritmo da spec em inteiros (maiores restos pelo resto da divisão inteira, o código desempata; a cada rodada só entram os SKUs que ainda têm disponível e, se nenhum deles vendeu, a divisão é igual). Participação = venda do SKU nos últimos `dias_mix_gondola` dias abertos (mesma regra de dia aberto da queda de venda, antes de hoje) dividida pela do produto; sem venda no produto, participação 0 e divisão igual. `Reposicao.mix` faz 5 leituras fixas (SKUs, capacidade, política, vendas diárias de todos, estoques), conferidas no teste de consultas fixas. Rotas: `GET /reposicao/produtos?busca=` (reposição; busca em qualquer SKU do produto, com a capacidade gravada), `GET /reposicao/produtos/{id}/mix?capacidade=` (reposição e comprador; `capacidade` e `capacidade_gravada` separadas, `dias_abertos`, SKUs da maior participação para a menor) e `PUT /reposicao/produtos/{id}/capacidade` (reposição); 404 sem SKU ativo, 422 com capacidade < 1. `produto_id` entrou em `/skus/{sku}/analise` e nos cards do `/reposicao/painel`. Pergunta 12 na política. UI: `gondola.html` (menu "Montar gôndola" do repositor: busca de produto sem `?produto`, mix com `?produto=`; recalcula ao digitar, "Lembrar este número" grava), link "Montar a gôndola deste produto" nos dois tipos de card do painel do repositor e bloco "Participação nas vendas do produto" na tela do SKU. Verificado em 390 px e desktop com o Rafa e a Carla: no seed, 12 lugares viram 4 marrons, 3 cinzas, 2 azuis, 2 beges e 1 branco (45% e 8%). README: o reset trunca `copilot.capacidades_gondola`. Banco local sem capacidade gravada. Suíte com 1233 testes verde; pyright com os mesmos 79 erros por arquivo.
