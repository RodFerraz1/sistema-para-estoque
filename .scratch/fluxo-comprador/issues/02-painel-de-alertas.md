# 02: Painel de alertas calculado

**What to build:** ao abrir o Copilot, o comprador chefe vê o **painel de alertas** sem apertar nenhum botão. Ele mostra os SKUs ativos com algum motivo de alerta da política ativa, os mais urgentes primeiro, com o que precisa para entender o problema sem abrir o SKU. Ainda não há avisos nem decisões de compra.

**Blocked by:** 01

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seção "Módulo novo `painel`", composição do painel)

- [x] Existe o módulo `painel` com o service que compõe o painel a partir de `purchasing`, `inventory`, `catalog` e da política ativa, sem chamar o Jev.
- [x] `GET /painel` devolve `alertas`, `decididos` (vazio por enquanto) e `skus_com_erro`.
- [x] Os motivos de cada SKU são os alertas da sugestão de pedido que estão nos motivos de alerta da política, mais `abaixo_do_piso_alerta` quando a cobertura atual está abaixo do piso de alerta e esse motivo está na política.
- [x] Ordem: primeiro os SKUs com ruptura antes da chegada, depois o resto. Dentro de cada grupo, a menor cobertura na chegada sem a compra primeiro, os SKUs sem cálculo no fim e desempate pelo código.
- [x] Cada item traz código, produto, cor, tamanho, disponível, cobertura atual, cobertura na chegada sem a compra, motivos, e quantidade e fornecedor sugeridos quando houver compra.
- [x] SKU inativo nunca aparece. SKU com `SKUSemEstoque` vai para `skus_com_erro` sem derrubar o painel.
- [x] Com o banco fora do ar, `GET /painel` responde 503 com mensagem.
- [x] `index.html` vira o painel: tabela legível, mensagem de "nada pedindo atenção" quando estiver vazio e mensagem clara de banco indisponível.
- [x] Testes HTTP com fakes cobrem a ordem, o motivo fora da política, o SKU inativo e o `skus_com_erro`. O teste de UI cobre a página.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões:

- **Módulo `src/painel/`**: o service é `Painel` (`painel() -> PainelDeAlertas`). Lê a política ativa uma vez, e para cada SKU ativo do `catalog` calcula a sugestão (`purchasing`), o disponível e a cobertura atual (`inventory`). Os motivos saem na ordem dos alertas da sugestão, com `abaixo_do_piso_alerta` no fim (cobertura atual estritamente abaixo de `piso_alerta_dias / 30`, como o `abaixo_do_piso` do `inventory`). SKU sem giro nunca fica abaixo do piso. Não há repositório neste ticket: avisos e decisões entram nos tickets 03 e 05. `decididos` sai vazio.
- **Grupo de urgência**: "ruptura antes da chegada" conta só quando é motivo da política, para a ordem bater com os selos que o comprador vê na linha.
- **503**: handler no app para `sqlalchemy.exc.OperationalError` (sem conexão com o Postgres), com mensagem de infraestrutura. Vale para todas as rotas, não só `/painel`, porque a tela do SKU e o aviso também precisam dele.
- **UI**: `index.html` virou o painel (`painel.js`), uma tabela com produto (nome, cor, tamanho, código), disponível, cobertura atual, cobertura na chegada sem a compra ("acaba antes" quando negativa, "sem cálculo" quando nula), selos dos motivos e a sugestão. Mensagens de vazio, de banco fora do ar (o texto do 503) e dos `skus_com_erro`. Os rótulos dos motivos e a formatação de cobertura ficaram em `comum.js`, para a tela do SKU usar. A navegação ficou Painel, Chat e Política (o chat sai no ticket 06).
- **Banco local**: `GET /painel` com o seed leva 2,2 s e traz 9 SKUs, todos com ruptura antes da chegada.
- `uv run pytest -q` com Postgres: 691 passando. Pyright sem erro novo.
