# 11: Queda de venda e painel do repositor

**What to build:** o repositor abre o Copilot no celular e vê os SKUs que provavelmente faltam na gôndola: os que vendiam com regularidade, pararam de vender nos últimos dias abertos e ainda têm estoque no ERP. Cada card mostra quanto vendia por dia, quanto vendeu nos últimos dias e o disponível, e os que mais perdem venda vêm primeiro. Um SKU com queda de venda e sem estoque não vai para o repositor: aparece para o comprador como ruptura ou entrega atrasada, com o selo "parou de vender".

**Blocked by:** 04, 06

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Repositor: queda de venda e verificação de gôndola")

- [ ] Módulo `reposicao` com a detecção em código (sem Jev): venda diária base nos 28 dias abertos anteriores, janela de `dias_observados_queda` dias abertos e fechados, dia aberto = a loja vendeu alguma coisa, venda diária mínima e limiar de Poisson.
- [ ] Parâmetros novos na política (`dias_observados_queda` 2, `venda_diaria_minima_queda` 1, `limiar_queda` 0,01), com migration, validação e uma pergunta na tela de política marcada "a validar com o comprador".
- [ ] `GET /reposicao/painel?busca=&categoria=` (papel `reposicao`), ordenado pela venda perdida estimada.
- [ ] O painel do comprador mostra o selo "parou de vender" nos SKUs com queda de venda e disponível zero.
- [ ] `reposicao.html`, mobile first como a página de aviso. Quem tem papel `reposicao` cai nela ao entrar.
- [ ] Testes HTTP com vendas diárias fake e relógio injetado: o tapete (λ 10, 5 e 0) entra, λ 0,3 com zero não entra, domingo sem venda na loja não conta, disponível zero vai para o comprador e não para o repositor, e 403 para os outros papéis.
- [ ] Verificado no navegador com o tapete marrom do seed. Typecheck e suíte completa verdes.
