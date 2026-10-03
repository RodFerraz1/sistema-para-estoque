# Usuários com login próprio, sessão em cookie e papéis fixos

Status: accepted (2026-10-03)

Até a spec 08, o Copilot não tinha login. O comprador chefe e as vendedoras digitavam o nome à mão. Com o repositor e a vendedora usando o Copilot no celular, e com preço de compra e negociação na mesma aplicação, cada pessoa precisa ver só o que é dela, e cada registro precisa dizer quem o fez.

Decidimos:

1. **Login próprio** com e-mail e senha (argon2id), num módulo `usuarios` do schema `copilot`. O admin cadastra as pessoas e redefine a senha delas. O primeiro admin é criado por um comando.
2. **Sessão em cookie** `HttpOnly` e `SameSite=Lax`, com token aleatório cujo hash fica no banco. A sessão vale 30 dias desde o último uso, para a vendedora não digitar a senha a cada aviso. Sair, ou desativar o usuário, revoga a sessão.
3. **Quatro papéis fixos** no código: `comprador`, `vendas`, `reposicao` e `admin`. Uma pessoa pode ter vários. As permissões são dependências do FastAPI por rota.

## Considered Options

- **JWT sem estado**: rejeitada. Não dá para revogar uma sessão (vendedora que saiu da empresa, celular perdido) sem montar uma lista de revogação, que traz o estado de volta.
- **Provedor externo (Auth0, Google, Keycloak)**: rejeitada por enquanto. As vendedoras e os repositores não têm conta corporativa, e é mais uma peça para operar num projeto de uma pessoa. Se houver integração com o Maos, o login dele pode substituir este.
- **Permissões configuráveis por tela**: rejeitada. São quatro funções conhecidas, e um editor de permissões é produto que ninguém pediu.

## Consequences

- Toda rota exige login, exceto `/health` e `/login`. Os testes HTTP trocam a dependência do usuário atual por um usuário fake com os papéis do cenário.
- Avisos, decisões, cobranças e verificações ganham `usuario_id`. Os nomes digitados antes continuam como estão no histórico.
- O link público da página de aviso deixa de existir: a vendedora entra com a conta dela.
