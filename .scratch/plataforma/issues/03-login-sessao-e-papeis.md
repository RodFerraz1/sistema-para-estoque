# 03: Login, sessão e papéis

**What to build:** o Copilot passa a exigir login (ADR-0007). Uma pessoa entra com e-mail e senha, a sessão dura 30 dias desde o último uso e cada pessoa cai na tela inicial do seu papel (comprador: painel; vendas: aviso). Toda rota exige login, exceto o health e o login, e cada rota exige o papel certo. O primeiro admin é criado por um comando.

**Blocked by:** 01

**Status:** done

**Spec:** `.scratch/plataforma/spec.md` (seção "Usuários, sessão e papéis")

- [x] Módulo `usuarios` no padrão dos módulos atuais (repositório como Protocol, versão em memória e Postgres). Migration com `usuarios`, `sessoes` e `tentativas_login`.
- [x] Senha com argon2id por uma biblioteca mantida. Sessão em cookie `HttpOnly`, `SameSite=Lax` e `Secure` fora do local, com só o hash do token no banco. Expira 30 dias depois do último uso e é renovada a cada uso.
- [x] `POST /login`, `POST /logout` e `GET /eu` (usuário logado com papéis). Bloqueio de 15 minutos depois de 5 tentativas erradas em 15 minutos para o mesmo e-mail.
- [x] Dependências `usuario_atual` (401) e `exige_papel` (403) aplicadas a todas as rotas existentes, com o mapa de permissões da spec. Mudanças de estado exigem `X-Requested-With`.
- [x] Comando que cria o primeiro admin pedindo a senha no terminal.
- [x] `login.html` e o redirecionamento da UI no primeiro 401 (`login.html?volta=...`). O cabeçalho mostra só os links dos papéis do usuário e um "Sair".
- [x] Os testes HTTP existentes passam a trocar `usuario_atual` por um usuário fake. Teste à parte para login, sessão expirada, sessão revogada, bloqueio, 401 e 403 de verdade. Contrato dos repositórios em memória e no Postgres.
- [x] Verificado no navegador, no desktop e no celular. Typecheck e suíte completa verdes.

## Comments

**2026-10-03 (agente):** módulo `src/usuarios` (schemas, service, repositório Protocol, em memória, Postgres, dependências), migration `0014_usuarios` (`usuarios`, `sessoes`, `tentativas_login`), argon2id com `argon2-cffi`, rotas `POST /login`, `POST /logout` e `GET /eu` em `src/api/usuarios.py`, comando `scripts/criar_admin.py`, `login.html`/`login.js` e o cabeçalho montado por `cabecalho(papel)` em `comum.js`. Decisões: o token vai no cookie `copilot_sessao` e o banco guarda o sha256 dele; `AMBIENTE=producao` liga o `Secure` (padrão `local`). O bloqueio conta só as falhas (tentativa durante o bloqueio não conta, para não estender) e um acerto zera as falhas; e-mail desconhecido conta e responde igual à senha errada. 401 sem sessão, 403 com papel errado, 429 no bloqueio. `exige_x_requested_with` é dependência do app inteiro (POST/PUT/PATCH/DELETE sem o cabeçalho dá 403, inclusive `/login`). Mapa aplicado: `GET /skus` (busca) para comprador, vendas e reposição; `POST /avisos` só vendas; todo o resto (painel, SKU, preços, decisões, política, chat, rag) só comprador; `/eu` e `/logout` para qualquer pessoa logada. `/docs` e `/openapi.json` continuam abertos (não têm dado). `notificacoes_vistas_ate` ficou para o ticket 10, que é dono dele. O botão "Página das vendedoras" do painel só aparece para quem tem `vendas` (`data-papel`); o "Copiar link" fica para o 04 tirar. O comando aceita `--papeis` (padrão `admin`) para criar pessoas de teste no local, e lê a senha do pipe sem terminal.

**Para os próximos tickets:**
- **Logar no app local:** já existem no banco local (senha `copilot-local`) `admin@copilot.local` (admin), `carla@copilot.local` (comprador) e `bia@copilot.local` (vendas). Para criar outra: `echo 'uma-senha' | uv run python -m scripts.criar_admin --nome "Rafa" --email rafa@copilot.local --papeis reposicao`.
- **Capturar telas logado:** `uv run python -m scripts.capturar_tela <url> <arquivo.png> --email carla@copilot.local --senha copilot-local` (faz o `POST /login`, põe o cookie no Chrome headless pelo DevTools e grava o PNG; sai sozinho). Celular: `--largura 390 --altura 844 --celular` (sem o truque do iframe). Também `--pagina-inteira` e `--espera <s>` (padrão 4 s depois do load). Sem `--email`, captura deslogado (cai no login). Para `curl`: `curl -c /tmp/c -H 'X-Requested-With: x' -H 'Content-Type: application/json' -d '{"email":"carla@copilot.local","senha":"copilot-local"}' localhost:8765/login` e depois `curl -b /tmp/c ...` (POST/PUT precisam do `X-Requested-With`).
- **Testes:** o `conftest.py` da raiz tem o fixture autouse `usuario_logado`: todo teste HTTP entra como um usuário fake com os quatro papéis e sem exigir `X-Requested-With`, sem boilerplate. Para restringir: `@pytest.mark.papeis("vendas")` no teste ou `pytestmark` no módulo; o fake vem no fixture `usuario_logado` (para conferir `avisado_por == usuario_logado.nome`, por exemplo). Para login de verdade: `@pytest.mark.login_de_verdade` (ver `src/api/tests/test_login.py`). Rota nova precisa de `exige_papel(...)`: o `test_toda_rota_exige_login_menos_o_health_e_o_login` e o `test_cada_rota_recusa_quem_nao_tem_o_papel_do_mapa` percorrem o OpenAPI e falham se faltar; rota que não é só do comprador entra no `PAPEIS_POR_ROTA` de `test_login.py`. Para usar o usuário no endpoint: `usuario: Usuario = Depends(exige_papel("vendas"))`.
- **UI:** cada página chama `cabecalho("<papel>")` (de `comum.js`), que monta o menu pelo `TELAS` e manda quem não tem o papel para a sua tela inicial. Tela nova entra no `TELAS` (a ordem define a tela inicial: comprador, vendas, ...) e o `<nav aria-label="Telas do Copilot"></nav>` vai vazio no HTML. `api()` manda o `X-Requested-With` e leva ao `login.html?volta=...` no primeiro 401.
- Desativar usuário e revogar todas as sessões dele (ticket 04) ainda não existe no repositório: falta um `revogar_do_usuario` nas sessões. O `Usuarios.usuario_da_sessao` já recusa usuário inativo.
- Suíte com 848 testes verde (smoke incluído). Pyright com os mesmos 79 erros por arquivo.
