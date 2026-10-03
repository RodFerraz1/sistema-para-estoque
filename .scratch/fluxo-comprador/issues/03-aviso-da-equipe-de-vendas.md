# 03: Aviso da equipe de vendas

**What to build:** uma vendedora da equipe de vendas abre a página de aviso no celular, busca o SKU pelo nome, marca `acabou` ou `vendendo muito`, escreve um comentário opcional e envia. O SKU aparece na hora no painel de alertas do comprador chefe, no primeiro grupo, mesmo que o cálculo não veja problema.

**Blocked by:** 02

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "Módulo novo `painel`", "Esquema", "`catalog`", "API" e "UI")

- [x] Tabela `avisos` no schema `copilot` (migration), com repositório em memória e Postgres e uma suíte de contrato rodando contra os dois.
- [x] `POST /avisos` responde 201, 404 para SKU inexistente e 422 para SKU inativo ou tipo inválido.
- [x] `catalog.buscar_skus`: SKUs ativos cujo código, produto, cor ou tamanho contêm todas as palavras, sem diferenciar acento nem maiúscula, no máximo 20, ordenados por produto, cor e tamanho. Exposto em `GET /skus?busca=`, com mínimo de 2 caracteres.
- [x] `GET /skus/{sku}/avisos` devolve os avisos abertos, os mais recentes primeiro. Aviso aberto é derivado (ainda não existem decisões, então todos estão abertos).
- [x] O painel inclui os SKUs com aviso aberto no primeiro grupo, marca os que estão lá só por aviso e mostra quantos avisos abertos há e qual foi o último (tipo e quem avisou).
- [x] `aviso.html`: mobile first, sem navegação e sem chat. Tem busca com debounce, dois botões grandes para o tipo, comentário, nome lembrado no `localStorage` (com try/catch), confirmação na página e formulário pronto para o próximo aviso.
- [x] O painel tem um link visível para a página de aviso, para compartilhar com a equipe de vendas.
- [x] Testes HTTP cobrem: aviso válido, SKU inexistente, SKU inativo, busca sem acento e SKU com aviso e sem motivo no primeiro grupo do painel. O teste de UI cobre `aviso.html`.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões:

- **Domínio**: `Aviso` e `TipoAviso` em `src/painel/schemas.py`; `AvisosRepositorio` com `gravar` e `listar(sku_code=None)` (mais recente primeiro, `id` desempata), em memória e Postgres; migration `0010_avisos` (checks de tipo e de `avisado_por` não vazio, índice `(sku_code, criado_em)`; downgrade testado). `Painel.registrar_aviso` lança `SKUNaoEncontrado` (404) e `SKUInativo` (422); comentário em branco vira nulo.
- **Relógio**: o service recebe um `relogio` (callable), injetado por `get_relogio`. Os testes usam `RelogioFake` (`tests/fakes.py`) para avançar o tempo entre avisos, o que o ticket 05 também precisa.
- **Painel**: lê todos os avisos de uma vez e agrupa por SKU (o volume do MVP é pequeno). Como ainda não há decisões, todo aviso está aberto. O item ganhou a lista de avisos abertos e `so_por_aviso` (com aviso e sem motivo). A resposta HTTP traz `avisos_abertos` (número), `ultimo_aviso` e `so_por_aviso`. O primeiro grupo passa a ser aviso aberto ou ruptura.
- **Busca**: `Catalog.buscar_skus` filtra em Python sobre `listar_skus` (os ativos), normalizando acento e maiúscula, para valer igual nos dois adapters. `GET /skus?busca=` exige 2 a 100 caracteres (sem `strip`: " b " passa e acha o que tiver "b").
- **Rotas**: `POST /avisos` e `GET /skus/{sku}/avisos` em `src/api/avisos.py`. `_sku_ou_404` de `skus.py` virou público para ser reaproveitado.
- **UI**: `aviso.html` + `aviso.js`, só com o nome do produto no topo (sem navegação nem chat), coluna estreita, alvos de toque de 52 a 64 px. Busca com espera de 300 ms e descarte de respostas atrasadas; cada resultado é um botão com produto, cor e tamanho; o escolhido fica destacado com "Trocar". Tipo em dois botões grandes (`aria-pressed`). O nome fica no `localStorage` com chave própria (`copilot.vendedora`, para não misturar com o nome do comprador no mesmo navegador), com try/catch. Depois de enviar, a confirmação fica na página e o formulário volta limpo, mantendo o nome. No painel: coluna "Avisos" (quantos abertos, tipo e autor do último, data), selo "Só por aviso" no lugar dos motivos e um cartão com o link da página de aviso.
- **Contrato**: `src/painel/tests/test_contrato_avisos.py` roda em memória e no Postgres (guarda e devolve as linhas existentes).
- `uv run pytest -q` com Postgres: 719 passando. Pyright sem erro novo.
