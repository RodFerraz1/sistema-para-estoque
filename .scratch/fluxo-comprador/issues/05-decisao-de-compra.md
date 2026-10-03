# 05: Decisão de compra

**What to build:** na tela do SKU, o comprador chefe registra a **decisão de compra**: `vou_comprar` (quantidade já preenchida com a sugestão e editável), `negociando` (comentário opcional) ou `nao_comprar_agora` (motivo obrigatório). A decisão fecha os avisos abertos do SKU e o tira do painel por 7 dias. Ele aparece na seção "decididos" e volta antes disso se chegar um aviso novo. O Copilot não cria pedido de compra.

**Blocked by:** 03, 04

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "Módulo novo `painel`", "Esquema", "API" e "UI")

- [x] Tabela `decisoes_compra` no schema `copilot` (migration), com check constraints espelhando as validações, repositório em memória e Postgres e uma suíte de contrato rodando contra os dois.
- [x] `POST /skus/{sku}/decisoes` responde 201 e grava `quantidade_sugerida` e `politica_versao` do momento. Responde 404 sem o SKU, e 422 para `vou_comprar` sem quantidade maior que zero ou `nao_comprar_agora` sem motivo.
- [x] `GET /skus/{sku}/decisoes` lista as decisões, as mais recentes primeiro.
- [x] Aviso aberto passa a ser o aviso sem decisão de compra posterior do mesmo SKU.
- [x] Decisão vigente é a mais recente, com menos de 7 dias (constante nomeada) e sem aviso posterior. SKU com decisão vigente sai de `alertas` e vai para `decididos`, com a decisão.
- [x] O painel mostra a seção "Decididos nos últimos 7 dias", recolhida por padrão.
- [x] A tela do SKU mostra os avisos abertos, as decisões anteriores e o formulário de decisão. Os campos mudam conforme o tipo, o nome é obrigatório e, depois de enviar, a tela volta ao painel.
- [x] Testes HTTP, com relógio injetado, cobrem:
  - a decisão tira o SKU de `alertas` e o põe em `decididos`;
  - a decisão fecha os avisos;
  - um aviso posterior traz o SKU de volta;
  - uma decisão com mais de 7 dias deixa de valer;
  - as validações de cada tipo.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Domínio**: `DecisaoCompra` e `TipoDecisao` em `src/painel/schemas.py`; `DecisoesRepositorio` com `gravar`, `listar(sku_code)` e `ultimas()` (a mais recente de cada SKU, `DISTINCT ON` no Postgres), em memória e Postgres; migration `0011_decisoes_compra` com os checks (tipo; quantidade só e sempre em `vou_comprar`, maior que zero; motivo não vazio em `nao_comprar_agora`; nome não vazio; sugerida não negativa). Downgrade testado.
- **Validação**: além do que a spec pede, quantidade em `negociando` ou `nao_comprar_agora` responde 422 (`QuantidadeSoParaComprar`), para a regra do banco ser a mesma do service. Motivo em branco conta como ausente. `quantidade_sugerida` é zero quando a sugestão do momento não tem compra.
- **Aviso aberto e decisão vigente** saem só das datas (`_abertos` e `_vigente` no service), com `PRAZO_DA_DECISAO = timedelta(days=7)`. Aviso com a mesma hora da decisão conta como fechado (só aviso estritamente posterior reabre).
- **Desvio, decididos**: a spec diz que o SKU entra no painel se tem aviso aberto ou motivo e, com decisão vigente, vai para `decididos`. Isso faria um SKU que só estava no painel por aviso (o caso de `nao_comprar_agora` depois de "vendendo muito") sumir também de `decididos`, contra a história 15 ("acompanhar o que decidi nos últimos 7 dias"). Implementei: toda decisão vigente põe o SKU em `decididos`, com ou sem motivo; quando ela vence (ou chega aviso novo), o SKU volta para `alertas` se ainda tiver motivo ou aviso. De quebra, o painel não calcula a sugestão dos decididos. `decididos` vem da decisão mais recente para a mais antiga.
- **Rotas**: todas as do módulo (`/painel`, `/avisos`, `/skus/{sku}/avisos`, `/skus/{sku}/decisoes`) ficaram num router só, `src/api/painel.py`.
- **UI**: na tela do SKU, blocos "Avisos abertos" (perto do topo), "Decisões anteriores" e o formulário "Decisão de compra" no fim, com o texto de que o Copilot não cria pedido. Escolher o tipo mostra a quantidade (pré-preenchida com a sugestão, com fornecedor e MOQ na ajuda) ou o motivo; comentário e nome (lembrado no `localStorage`) valem para todos. Depois de registrar, vai para o painel. No painel, `<details>` recolhido "Decididos nos últimos 7 dias (N)" com a decisão, quem e quando.
- **Verificação manual** (Chrome, banco local): `ED-BEGE-CASAL-01` com `vou_comprar` 200 un. (sugestão 193); o painel abriu com o SKU fora dos alertas e dentro de "Decididos", recolhido. A decisão de teste foi apagada depois.
- `uv run pytest -q` com Postgres: 771 passando. Pyright sem erro novo.
