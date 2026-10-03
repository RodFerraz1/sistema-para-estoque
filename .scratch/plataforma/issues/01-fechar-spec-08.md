# 01: Fechar a spec 08 (fluxo do comprador)

**What to build:** pré-requisito da plataforma. O fluxo do comprador da spec 08 (painel de alertas, aviso, tela do SKU, decisão de compra, chat lateral) está pronto no working tree, mas o ticket 07 de `.scratch/fluxo-comprador/` ficou `in-progress` e nada foi commitado. Este ticket termina o ticket 07, verifica tudo e deixa o trabalho commitado, para a spec 09 partir de uma base estável.

**Blocked by:** None (can start immediately)

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Pré-requisito"); `.scratch/fluxo-comprador/issues/07-smoke-readme-e-demo.md`

- [x] Os checkboxes que faltam no ticket 07 da spec 08 estão feitos, e ele está `Status: done`.
- [x] Suíte completa, smoke contra o Postgres e pyright sem erro novo.
- [x] O trabalho da spec 08 está commitado (pedir confirmação ao dev antes do commit, se ele estiver presente), separado dos arquivos de planejamento da spec 09.

## Comments

**2026-10-03 (agente):** ticket 07 da spec 08 fechado: as quatro capturas refeitas no visual novo da UI (as de 2026-10-01 eram anteriores ao redesenho), README atualizado com as telas novas, `docs/demo.md` reescrito no fluxo aviso, painel, tela do SKU, chat em contexto, preços e decisão (números conferidos contra o banco), `module-interfaces.md` com `painel` no lugar de `aprovacao` e o ERP só leitura. O aviso de demonstração antigo já não existia; usei um temporário no `ED-BEGE-CASAL-01` e apaguei. Ficam no banco dois avisos do dev (`LT-PRET-ÚNICO-02`, `PDPE-ESTA-4565-01`) e uma decisão (`TBC-CINZ-70140-06`), que não toquei. Commits: `fc4e576` (spec 08) e o de planejamento. O `CONTEXT.md` foi dividido: os termos do fluxo do comprador foram no commit da spec 08; cobertura em dias, ruptura, lead time ignorado, similar, entrega atrasada, cobrança, operação da loja e usuários e notificações foram no commit de planejamento. Para os próximos tickets: suíte com 792 testes verde (smoke incluído). Pyright agora dá 79 erros, todos antigos: o baseline de 71 do brief foi medido com outra versão do pyright (com a atual, o HEAD anterior dava 91). Compare por arquivo, não pelo total. Para capturar a página de aviso a 390 px, use um iframe de 390 px numa janela mais larga e recorte: o Chrome headless não abre janela tão estreita e a captura direta sai cortada.

