# 10: Notificações: episódios, varredura, sino e pop-up

**What to build:** o comprador chefe é avisado sem precisar olhar o painel. Quando um SKU entra em ruptura, quando uma entrega atrasa ou quando chega aviso da equipe de vendas, nasce uma notificação. Ela aparece no sino do cabeçalho, com o número de não lidas, e num pop-up que agrupa por tipo ("5 SKUs entraram em ruptura") quando há coisa nova desde a última vez, ao abrir o Copilot ou com ele aberto. Cada condição notifica uma vez enquanto durar e de novo se voltar.

**Blocked by:** 04, 09

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Episódios de alerta e notificações")

- [ ] Tabela `episodios_alerta` com índice único parcial para não haver dois abertos da mesma condição. O usuário ganha o cursor `notificacoes_vistas_ate`.
- [ ] Varredura idempotente, com lock consultivo do Postgres, que abre e fecha episódios de `ruptura` e `entrega_atrasada` a partir do retrato. SKU com decisão de compra vigente não abre episódio de ruptura. Avisos abrem episódio `aviso` na hora em que são registrados.
- [ ] `GET /notificacoes` (roda a varredura e devolve as dos papéis do usuário, com o total de não lidas) e `POST /notificacoes/vistas`.
- [ ] Sino em todas as telas logadas, com a lista e o link de cada notificação para o SKU ou para a entrega. Consulta ao abrir a tela e a cada 2 minutos com a aba visível. Pop-up que agrupa por tipo, fecha sozinho e não bloqueia a tela.
- [ ] Testes: entrar abre, varrer de novo não duplica, sair fecha, voltar abre outro, decisão vigente impede, o cursor separa lidas de não lidas, papel errado não vê. No Postgres: duas varreduras simultâneas não duplicam.
- [ ] Verificado no navegador. Typecheck e suíte completa verdes.
