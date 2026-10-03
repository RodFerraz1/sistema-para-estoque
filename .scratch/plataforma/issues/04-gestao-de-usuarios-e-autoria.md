# 04: Gestão de usuários e autoria pelo usuário logado

**What to build:** o admin cadastra pessoas, dá papéis, desativa e redefine senha numa tela própria. Cada pessoa troca a própria senha. Avisos e decisões de compra deixam de pedir o nome: registram o usuário logado. O chat registra quem perguntou. Quem tem mais de um papel alterna entre as telas pelo menu.

**Blocked by:** 03

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Usuários, sessão e papéis")

- [ ] Rotas de admin: listar (com papéis, situação e último acesso), criar, editar papéis, desativar (revoga as sessões) e redefinir senha. `PUT /eu/senha` para trocar a própria senha.
- [ ] `usuarios.html` (admin) e `conta.html` (trocar senha e sair), no visual de `estilo.css`.
- [ ] Migration: `avisos`, `decisoes_compra` e `registros_decisao` ganham `usuario_id` opcional. As linhas antigas ficam como estão.
- [ ] `POST /avisos` e `POST /skus/{sku}/decisoes` deixam de aceitar o nome no corpo e preenchem `avisado_por`/`decidido_por` com o nome do usuário logado. A página de aviso perde o campo de nome e o `localStorage` dele. Some o link público "Copiar link" do painel.
- [ ] Testes HTTP: admin cria e desativa, não-admin recebe 403, o usuário desativado não entra, o aviso grava o usuário logado, e o histórico antigo continua com o nome digitado.
- [ ] Verificado no navegador. Typecheck e suíte completa verdes.
