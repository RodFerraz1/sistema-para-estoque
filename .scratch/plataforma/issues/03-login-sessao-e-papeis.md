# 03: Login, sessão e papéis

**What to build:** o Copilot passa a exigir login (ADR-0007). Uma pessoa entra com e-mail e senha, a sessão dura 30 dias desde o último uso e cada pessoa cai na tela inicial do seu papel (comprador: painel; vendas: aviso). Toda rota exige login, exceto o health e o login, e cada rota exige o papel certo. O primeiro admin é criado por um comando.

**Blocked by:** 01

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Usuários, sessão e papéis")

- [ ] Módulo `usuarios` no padrão dos módulos atuais (repositório como Protocol, versão em memória e Postgres). Migration com `usuarios`, `sessoes` e `tentativas_login`.
- [ ] Senha com argon2id por uma biblioteca mantida. Sessão em cookie `HttpOnly`, `SameSite=Lax` e `Secure` fora do local, com só o hash do token no banco. Expira 30 dias depois do último uso e é renovada a cada uso.
- [ ] `POST /login`, `POST /logout` e `GET /eu` (usuário logado com papéis). Bloqueio de 15 minutos depois de 5 tentativas erradas em 15 minutos para o mesmo e-mail.
- [ ] Dependências `usuario_atual` (401) e `exige_papel` (403) aplicadas a todas as rotas existentes, com o mapa de permissões da spec. Mudanças de estado exigem `X-Requested-With`.
- [ ] Comando que cria o primeiro admin pedindo a senha no terminal.
- [ ] `login.html` e o redirecionamento da UI no primeiro 401 (`login.html?volta=...`). O cabeçalho mostra só os links dos papéis do usuário e um "Sair".
- [ ] Os testes HTTP existentes passam a trocar `usuario_atual` por um usuário fake. Teste à parte para login, sessão expirada, sessão revogada, bloqueio, 401 e 403 de verdade. Contrato dos repositórios em memória e no Postgres.
- [ ] Verificado no navegador, no desktop e no celular. Typecheck e suíte completa verdes.
