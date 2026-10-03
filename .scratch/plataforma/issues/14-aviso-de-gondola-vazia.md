# 14: Aviso de gôndola vazia e setores

**What to build:** a vendedora que vê uma gôndola vazia busca o SKU, escolhe o setor da loja (já preenchido quando o Copilot sabe onde o SKU fica) e avisa o repositor em poucos toques. O aviso entra no topo do painel do repositor, com notificação na hora. A verificação de gôndola do repositor fecha o aviso, e a vendedora é notificada e vê o resultado em "Meus avisos". O repositor filtra o painel por setor para fazer a ronda. O admin mantém a lista de setores.

**Blocked by:** 12, 13

**Status:** ready-for-agent

**Spec:** `.scratch/plataforma/spec.md` (seção "Aviso de gôndola vazia e setores")

- [ ] Tabelas `setores`, `setores_sku` e `avisos_gondola` no schema `copilot`, com migration. O seed cria setores de exemplo e o setor dos SKUs dos cenários.
- [ ] `GET/POST/PUT /setores` (admin, com a lista de ativos legível pelos papéis `vendas` e `reposicao`), `POST /avisos-gondola` (vendas: 404 sem SKU, 422 para SKU ou setor inativo) e `GET /skus/{sku_code}/setor`.
- [ ] Aviso de gôndola aberto derivado das datas: aberto até uma verificação de gôndola posterior do mesmo SKU. A verificação aceita `setor_id` opcional, que corrige o setor do SKU.
- [ ] Painel do repositor com o grupo "Avisos das vendedoras" no topo (mais antigo primeiro), SKU com aviso e queda de venda aparecendo uma vez com os dois selos, setor em cada card e o filtro `setor`.
- [ ] Episódios `gondola_vazia` (para `reposicao`, na hora do aviso) e `verificacao_sobre_aviso` (para a vendedora autora). `GET /avisos/meus` junta os dois tipos de aviso com o seu desfecho.
- [ ] UI da vendedora: botão "gôndola vazia" no resultado da busca, passo com setor e comentário, e alerta (sem bloquear) quando o ERP diz disponível zero. Tela de setores para o admin.
- [ ] Testes HTTP: os cenários "Aviso de gôndola vazia" da spec e as permissões das rotas novas. Contrato dos repositórios de setores e avisos de gôndola em memória e no Postgres.
- [ ] Verificado no navegador, no celular, com a vendedora e o repositor. Typecheck e suíte completa verdes.
