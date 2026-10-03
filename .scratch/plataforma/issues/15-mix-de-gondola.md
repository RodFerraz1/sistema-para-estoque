# 15: Mix de gôndola

**What to build:** o repositor abre um produto (pelo card de um SKU no painel ou pela aba "Montar gôndola"), informa quantas peças cabem na gôndola e vê quantas de cada cor e tamanho colocar, pela participação de cada SKU nas vendas: 10 marrons e 2 brancos, e não 5 de cada. Toda cor com estoque ganha ao menos uma peça, nada passa do disponível e o Copilot lembra a capacidade do produto. O comprador chefe vê a mesma participação nas vendas na tela do SKU, para comprar a grade na proporção do que vende.

**Blocked by:** 11

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Mix de gôndola")

- [ ] Parâmetro `dias_mix_gondola` (padrão 90) na política, com migration. Tabela `capacidades_gondola` com `usuario_id`.
- [ ] Cálculo do mix no módulo `reposicao`, com o algoritmo da spec (uma peça por elegível, maiores restos, limite do disponível com redistribuição, desempate pelo código, divisão igual sem venda).
- [ ] `GET /reposicao/produtos?busca=`, `GET /reposicao/produtos/{produto_id}/mix?capacidade=` e `PUT /reposicao/produtos/{produto_id}/capacidade`.
- [ ] `gondola.html` mobile first, aba "Montar gôndola" no painel do repositor e link "Montar a gôndola deste produto" nos cards.
- [ ] Participação nas vendas do SKU e das outras cores e tamanhos do produto na tela do SKU do comprador.
- [ ] Testes HTTP: os cenários "Mix de gôndola" da spec e as permissões. Contrato do repositório de capacidades em memória e no Postgres.
- [ ] Verificado no navegador, no celular, com o tapete do seed. Typecheck e suíte completa verdes.
