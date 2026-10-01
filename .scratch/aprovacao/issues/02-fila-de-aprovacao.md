# 02: Fila de aprovação

**Status:** done
**Blocked by:** 01
**Spec:** `.scratch/aprovacao/spec.md` (seção "Fila de aprovação")

## What to build

Módulo `aprovacao`: gera sugestões para todos os SKUs ativos, guarda as com quantidade na fila com sinais do corpus e faixa, ordena com destaque para quem tem alerta, e registra a decisão humana. Aprovar cria o pedido no ERP; rejeitar exige motivo.

## Acceptance criteria

- [x] Migration `0007` com `copilot.sugestoes_fila` e o índice da spec.
- [x] `src/aprovacao/`: DTOs (`SugestaoNaFila`, `ResultadoGeracao`), port do repositório com Postgres e in-memory (teste de contrato), serviço `Aprovacao` (`gerar_fila`, `listar`, `carregar`, `aprovar`, `rejeitar`) e exceções (`SugestaoJaDecidida`, `JustificativaObrigatoria`, quantidade abaixo do MOQ).
- [x] Endpoints de `src/api/aprovacao.py` com os códigos da spec, router registrado.
- [x] Testes da spec (serviço com adapters em memória, contrato, HTTP).
- [x] `uv run pytest -q -m "not externo"` verde.

## Comments

**2026-09-30 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Ordem pela urgência** (desvio de nome e de conta): a spec ordenava por `cobertura_na_chegada_meses`, mas no código esse campo da `MemoriaCalculo` já inclui a compra e fica perto de piso + ciclo para quase todo SKU, então não mede urgência. A fila ordena pela cobertura na chegada **sem** a compra, `(posição - consumo no lead time) / giro`, que fica negativa quando o estoque acaba antes da chegada (o `estoque_na_chegada` para em zero e empataria todas as rupturas). Virou a propriedade `MemoriaCalculo.cobertura_na_chegada_sem_compra_meses` no `purchasing`, dono da conta, e a coluna `cobertura_na_chegada_sem_compra_meses` da tabela, com o índice `(status, destaque DESC, cobertura_na_chegada_sem_compra_meses)`. Desempate pelo `sku_code` (`COLLATE "C"` no Postgres, para bater com o in-memory).
- **Destaque**: a spec dizia "algum alerta do `purchasing`", mas no seed toda sugestão com compra tem o alerta de época forte e quase todas o de pedido mínimo, então tudo ficaria destacado. Segui a história 2 da spec (ruptura, teto, prazo e sinais): destacam `ruptura_antes_da_chegada`, `viola_teto`, `lead_time_observado_acima_do_contratado` (constante `ALERTAS_DE_DESTAQUE`) e qualquer sinal do corpus. É mecanismo de ordenação, não regra de estoque, por isso não virou parâmetro da política. Mesmo assim, na geração real contra o seed (31 sugestões, 38 s com o Jev), 30 ficaram em destaque, por causa do lead time observado e dos sinais. Se o comprador achar que o destaque perdeu o sentido, o próximo passo é tirar o lead time da lista ou exigir dois motivos.
- **Substituição**: gerar de novo marca como `substituida` **todas** as pendentes, e não só as dos SKUs que voltaram a ter compra. Um SKU que deixou de precisar de compra (estoque chegou, pedido aprovado) também sai da fila, que é o que "refletir os dados de agora" pede. As decididas não mudam. Substituída fica sem `decidido_em`.
- **Faixa na aprovação**: sempre recalculada com `purchasing.faixa_aprovacao(sugestao, quantidade)` (política ativa e histórico do fornecedor no momento da aprovação), com ou sem edição, e gravada no lugar da faixa da geração. A justificativa é validada contra essa faixa: uma sugestão que entrou na faixa 1 pode exigir justificativa na aprovação (ex.: quantidade editada acima do teto). Justificativa em branco conta como ausente; quando a faixa não exige, a informada é gravada.
- **Exceções**: `SugestaoNaoEncontrada(LookupError)`, `SugestaoJaDecidida` e `JustificativaObrigatoria(ValueError)` em `src/aprovacao/service.py`. Para quantidade zero ou abaixo do MOQ, reaproveitei a `QuantidadeInvalida` do `purchasing` em vez de criar outra (422). Nome ou motivo em branco dá `ValueError` no serviço e 422 na validação do corpo HTTP.
- **Sinais na geração**: `Aprovacao(catalog, purchasing, fila, *, now=None)` e `gerar_fila(sinais: SinaisCorpus)`, com os sinais na chamada. Motivo: `get_sinais_corpus` carrega o modelo de embedding (~220 MB) e exige o Jev, e listar, aprovar e rejeitar não precisam de nenhum dos dois. Uma chamada a `para_sugestoes` com todos os pares, então os sinais saem uma vez por par (fornecedor, produto). `DecisaoIndisponivel` durante o cálculo vira `sinais_indisponiveis: true` com `sinais` nulos.
- **Limitação: sem `JEV_KEY`**, `POST /sugestoes/gerar` responde 503 como os outros endpoints que usam o Jev, porque a dependência `get_decision_model` lança antes do endpoint rodar. Com o Jev configurado e fora do ar, responde 200 com `sinais_indisponiveis`, como a spec pede. Resolver o caso sem chave exigiria mudar a dependência do Jev para todos os endpoints, fora do escopo.
- **Concorrência**: `registrar_decisao` só grava se a sugestão ainda está `pendente` (`UPDATE ... WHERE status = 'pendente'`) e o serviço confere o status antes de chamar o ERP. Se duas aprovações da mesma sugestão correrem ao mesmo tempo, a segunda recebe 409, mas o pedido dela já pode ter sido criado no ERP (as duas bases são sistemas separados, sem transação comum). O pedido órfão fica com o id da sugestão na observação. Aceito para o MVP, que tem um comprador e nenhuma autenticação.
- **`listar`**: pendentes na ordem da fila; aprovadas, rejeitadas e substituídas da decisão mais recente para a mais antiga (substituídas, sem decisão, pela criação mais recente). `GET /sugestoes` aceita `status` = `pendente` (padrão), `aprovada`, `rejeitada` ou `substituida`.
- **`SugestaoNaFila`**: `sku: SKU`, `sugestao: SugestaoComSinais`, `faixa: FaixaAprovacao` e os campos de decisão; `sku_code` e a cobertura sem a compra são propriedades. Um validador recusa sugestão sem compra ou de outro SKU. No Postgres, `dados` (jsonb) guarda `{sku, sugestao}`; a tabela também tem checks de `status` e de `quantidade_aprovada > 0`. Sem FK para `erp.pedidos_compra`, porque o ERP é outro sistema.
- **Resposta HTTP** (`SugestaoNaFilaResponse` em `src/api/schemas.py`): `id`, `criado_em`, `status`, `destaque`, `sku_code`, `produto_nome`, `cobertura_na_chegada_sem_compra_meses`, `sugestao` (o `SugestaoComSinaisResponse` do M6, com fornecedor, quantidade, `valor_estimado_centavos`, `calculo`, alertas e sinais com os ids dos trechos), `faixa` (`faixa`, `aprovadores`, `exige_justificativa`, `ajustes`) e os campos de decisão. `SKUSemEstoque` na geração dá 500, como em `/skus`.
- **Migration `0007_sugestoes_fila`**: aplicada no Postgres local, com downgrade e upgrade testados. Rodei uma geração real contra o seed (resultado acima) e apaguei as linhas depois.
- **Testes**: serviço com adapters em memória (`src/aprovacao/tests/test_aprovacao.py`), contrato da fila contra in-memory e Postgres (`test_contrato_fila.py`), HTTP (`src/api/tests/test_aprovacao.py`, com as vendas relativas ao mês corrente para não depender da data) e a propriedade nova em `test_purchasing.py`. `uv run pytest -q -m "not externo"` com 703 passando (eram 625). Não mexi em nada externo, então não rodei `-m externo`.
- **`CONTEXT.md`**: verbete novo "Fila de aprovação".
