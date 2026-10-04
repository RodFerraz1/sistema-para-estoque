# 04: Gestão de usuários e autoria pelo usuário logado

**What to build:** o admin cadastra pessoas, dá papéis, desativa e redefine senha numa tela própria. Cada pessoa troca a própria senha. Avisos e decisões de compra deixam de pedir o nome: registram o usuário logado. O chat registra quem perguntou. Quem tem mais de um papel alterna entre as telas pelo menu.

**Blocked by:** 03

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Usuários, sessão e papéis")

- [x] Rotas de admin: listar (com papéis, situação e último acesso), criar, editar papéis, desativar (revoga as sessões) e redefinir senha. `PUT /eu/senha` para trocar a própria senha.
- [x] `usuarios.html` (admin) e `conta.html` (trocar senha e sair), no visual de `estilo.css`.
- [x] Migration: `avisos`, `decisoes_compra` e `registros_decisao` ganham `usuario_id` opcional. As linhas antigas ficam como estão.
- [x] `POST /avisos` e `POST /skus/{sku}/decisoes` deixam de aceitar o nome no corpo e preenchem `avisado_por`/`decidido_por` com o nome do usuário logado. A página de aviso perde o campo de nome e o `localStorage` dele. Some o link público "Copiar link" do painel.
- [x] Testes HTTP: admin cria e desativa, não-admin recebe 403, o usuário desativado não entra, o aviso grava o usuário logado, e o histórico antigo continua com o nome digitado.
- [x] Verificado no navegador. Typecheck e suíte completa verdes.

## Comments

**2026-10-03 (agente):** rotas de admin em `src/api/usuarios.py`: `GET/POST /usuarios`, `PUT /usuarios/{id}/papeis`, `POST /usuarios/{id}/desativar`, `POST /usuarios/{id}/reativar` e `PUT /usuarios/{id}/senha` (todas `exige_papel("admin")`), e `PUT /eu/senha` (qualquer pessoa logada, pede a senha atual; erro responde 422, nunca 401, para a UI não mandar ao login). No repositório: `UsuariosRepositorio.listar/atualizar` e `SessoesRepositorio.revogar_do_usuario`, com contrato em memória e Postgres. Desativar revoga todas as sessões; reativar não revive as antigas. Migration `0015_autoria`: `usuario_id` opcional com FK para `copilot.usuarios` (e índice) em `avisos`, `decisoes_compra` e `registros_decisao`. `Painel.registrar_aviso/registrar_decisao` recebem o `Usuario` autor (grava `avisado_por`/`decidido_por` com o nome e o `usuario_id`); o corpo não tem mais o nome (um nome enviado é ignorado, para JS antigo em cache não quebrar). `Copilot.responder(..., usuario_id)` grava quem perguntou. Telas `usuarios.html` (admin, no menu como "Usuários") e `conta.html` (o nome no cabeçalho leva a ela; no celular o nome aparece truncado); a página de aviso e a tela do SKU perderam o campo de nome e o `localStorage`, e o painel perdeu o "Copiar link". Decisões fora do texto do ticket: o admin não desativa a si mesmo nem tira o próprio papel de admin (422), "Reativar" existe porque o protótipo mostra, e redefinir/trocar a senha não revoga sessões.

**Para os próximos tickets:**
- **FK de `usuario_id`:** quem grava linha com `usuario_id` precisa do usuário no banco. O smoke grava o usuário fake do `conftest.py` (desativado, "Testes automáticos") no `copilot.usuarios` local; os contratos usam `tests/autor_no_banco.py` (`AUTOR` e `autor_no_banco()`), que cobranças e verificações podem reaproveitar.
- **Autor no serviço:** siga o padrão `autor: Usuario` (vindo de `usuario: Usuario = Depends(exige_papel(...))` na rota) em vez de nome no corpo.
- **Testes com login de verdade:** `src/api/tests/cenario_usuarios.py` tem `Cenario`, `cenario`, `client` e `entrar` (o `test_login.py` passou a importar dele).
- README: só corrigi as linhas de `/avisos` e `/skus/{sku}/decisoes`. As rotas novas de login e usuários e o `docs/demo.md` (curls com `avisado_por`/`decidido_por` e sem cookie) ficam para o ticket 16.
- Suíte com 890 testes verde (smoke incluído). Pyright com os mesmos 79 erros por arquivo.
