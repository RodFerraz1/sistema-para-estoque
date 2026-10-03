# 07: Smoke no Postgres, README e roteiro de demo

**What to build:** quem avaliar o projeto encontra o fluxo novo documentado e verificado contra o banco real: aviso pelo celular, painel de alertas, tela do SKU, chat em contexto e decisão de compra.

**Blocked by:** 05, 06

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "Documentação" e "Testing Decisions")

- [x] O smoke test contra o Postgres registra um aviso, confere o SKU no painel, registra uma decisão de compra e confere que o SKU saiu de `alertas` e entrou em `decididos`.
- [x] O README descreve o fluxo novo e as telas. As screenshots da fila são trocadas pelas do painel, da tela do SKU e da página de aviso.
- [x] O roteiro de demo segue o fluxo: a vendedora avisa, o comprador vê o painel, abre o SKU, pergunta no chat, olha os preços e registra a decisão.
- [x] Nenhuma menção restante a fila de aprovação, faixa de aprovação ou "aprovar cria pedido" em README, roteiro ou UI.
- [x] Typecheck, suíte completa e smoke verdes.

## Comments

**2026-10-01 (agente, handoff para a próxima sessão):** tickets 01 a 06 prontos (ver os comentários deles). Neste ticket:

- [x] Smoke novo `tests/smoke/test_painel.py` (aviso, painel, decisão, preços), verde e limpando o que cria.
- [x] Seed: preço pago nos pedidos antigos 1% abaixo do atual por mês de idade (`PRECO_SOBE_POR_MES` em `scripts/seed.py`, sem chamar o `rng`).
- [x] README: topo, reset, testes, tabela de endpoints, exemplos JSON, política, chat (identificação com contexto), seção nova "Fluxo do comprador", "UI", "Limites conhecidos do fluxo do comprador" e estrutura de módulos. Falta conferir de novo com `grep -n -i "fila\|aprova\|chat.html\|faixa de aprov\|sugestoes\|destaque" README.md`.
- [x] `docs/img/painel.png` capturada (com um aviso de demonstração no `TBC-BEGE-70140-01`).
- [x] Capturar `docs/img/sku.png` (1280x1400, `sku.html?sku=ED-BEGE-CASAL-01`), `docs/img/aviso.png` (390x844) e `docs/img/politica.png` (1280x900). O Chrome headless (`--headless=new --screenshot ... --virtual-time-budget=20000`) grava o arquivo mas não sai sozinho: rodar cada captura em background e matar o processo depois que o arquivo aparecer. O app está em `uv run uvicorn src.main:app --port 8765 --reload`.
- [x] Apagar o aviso de demonstração depois das capturas: `DELETE FROM copilot.avisos WHERE id = 'c4b92247-9d98-487d-abf3-ccf882e61040'`. Apagar `docs/img/fila.png` (`git rm`).
- [x] Reescrever `docs/demo.md` no fluxo novo: a vendedora avisa (aviso.html), o comprador vê o painel, abre o SKU (sugestão `ED-BEGE-CASAL-01`, que tem histórico de preço), pergunta no chat lateral ("por que está acabando?"), olha os preços e registra a decisão. Tirar `POST /sugestoes/gerar`, `chat.html` e "migrations até a 0008" (agora 0012).
- [x] Atualizar `.scratch/copilot-compras/module-interfaces.md` (bullets de `aprovacao`, `purchasing -> erp_adapter`, ações irreversíveis) para o módulo `painel` e o ERP só leitura.
- [x] Rodar `uv run pytest -q` (com o Postgres do `docker compose up -d db`), o smoke e o pyright (`uvx pyright --pythonpath .venv/bin/python src tests scripts`; o HEAD tinha 78 erros antigos, agora 71, nenhum novo). Marcar os checkboxes acima do ticket e fechar com `Status: done`.
- Nada foi commitado: todo o trabalho dos 7 tickets está no working tree da branch `m5-m8`.

**2026-10-03 (agente, fechamento):** as capturas do dia 1 estavam desatualizadas depois do redesenho da UI de 2026-10-02, então refiz as quatro (`painel`, `sku`, `aviso`, `politica`) com um aviso temporário no `ED-BEGE-CASAL-01`, apagado depois (o aviso de demonstração antigo já não existia no banco). A página de aviso foi capturada dentro de um iframe de 390 px, porque o Chrome headless não abre janela tão estreita e a captura direta cortava a página. O README ganhou as descrições do visual novo (painel em grupos de cards, tela do SKU em duas colunas, chat em conversa) e alt texts que batem com as imagens. `docs/demo.md` foi reescrito no fluxo novo, com números conferidos em 2026-10-03 rodando o fluxo contra o banco (aviso, painel, chat em contexto, preços e decisão, apagados no fim). `module-interfaces.md` trocou `aprovacao` por `painel` e o ERP passou a ser só leitura. Corrigi um erro de tipo novo em `src/ai/tests/test_chat.py` (`tipo: TipoAviso`). Suíte: 792 passed (smoke incluído, 21 no `tests/smoke`). Pyright: 79 erros, todos antigos; com a versão atual do pyright o HEAD dá 91 (não 78), e nenhum arquivo tem mais erro que no HEAD.
