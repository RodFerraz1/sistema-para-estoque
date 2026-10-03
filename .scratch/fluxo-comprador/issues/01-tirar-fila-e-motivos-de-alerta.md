# 01: Tirar a fila de aprovação e trocar os motivos de destaque por motivos de alerta

**What to build:** prefactor do fluxo novo (ADR-0005). Saem do produto a fila de aprovação, a faixa de aprovação e a criação de pedido de compra no ERP fake, e o ERP fake passa a ser só leitura para o Copilot. A política de compra troca os motivos de destaque por **motivos de alerta**, perde os limites das faixas e passa a ter ciclo de compra padrão de 2 meses. O comprador ainda usa o chat e a política normalmente. A home vira, por enquanto, uma página simples com links para as duas.

**Blocked by:** None (can start immediately)

**Status:** done

**Spec:** `.scratch/fluxo-comprador/spec.md` (seções "Política de compra", "`purchasing`", "`erp_adapter`" e "Esquema")

- [x] O router `/sugestoes`, o módulo `aprovacao`, a faixa de aprovação (cálculo, schema, conversores, testes) e `submeter_pedido` deixam de existir.
- [x] `criar_pedido_compra` sai da porta do ERP e das duas implementações. `fornecedor_tem_pedido` sai se ficar sem uso.
- [x] `MotivoDestaque` vira `MotivoAlerta`, com os valores de `TipoAlerta` mais `abaixo_do_piso_alerta`. Os motivos do corpus saem.
- [x] `ParametrosPolitica` perde as faixas e passa a ter `motivos_de_alerta`, com padrão `ruptura_antes_da_chegada` e `abaixo_do_piso_alerta`, e `ciclo_compra_meses` padrão 2.0. A validação entre campos continua passando com o padrão.
- [x] Uma migration remove `sugestoes_fila` e as colunas de faixa, renomeia a coluna de motivos e converte os valores das versões gravadas (descarta os do corpus e acrescenta `abaixo_do_piso_alerta`). O downgrade funciona.
- [x] `GET/PUT /politica-compra` e a tela de política mostram os motivos de alerta e não mostram faixas.
- [x] A home deixa de ser a fila e vira uma página provisória com links para chat e política. `fila.js` sai.
- [x] O teste de UI não acha nenhuma chamada `api(...)` para rota inexistente.
- [x] O smoke test da fila sai (o substituto vem no ticket 07).
- [x] Typecheck e suíte completa verdes.

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões e desvios:

- **Removidos**: `src/aprovacao/`, `src/api/aprovacao.py`, `src/purchasing/faixa.py`, `FaixaAprovacao`, `submeter_pedido`, `politica_da` (só a fila usava), `QuantidadeInvalida`/`SugestaoSemCompra`, `src/erp_adapter/schemas.py` (`ItemNovoPedido`), `criar_pedido_compra` e `fornecedor_tem_pedido` (sem uso depois da faixa) da porta e das duas implementações, os DTOs HTTP da fila e da faixa, `fila.js` e os testes de tudo isso (inclusive `test_contrato_pedido_compra.py` e o smoke da fila). `PedidoCompra` em memória perdeu os campos que só a criação de pedido gravava.
- **Migration `0009_motivos_de_alerta`**: apaga `sugestoes_fila` e as colunas de faixa, renomeia `motivos_de_destaque` para `motivos_de_alerta` em todas as versões (tira os motivos do corpus, mantém a ordem dos outros e acrescenta `abaixo_do_piso_alerta` no fim) e troca a constraint. A "versão padrão" é a v1 enquanto ela ainda tem os valores originais (ciclo 1,0 e `{ruptura, viola_teto}`): ela vira o padrão novo inteiro (ciclo 2,0 e `{ruptura, abaixo_do_piso_alerta}`), para o v1 do banco continuar igual a `PARAMETROS_V1` (o teste do Postgres confere isso). Versões gravadas pelo comprador só ganham a conversão dos motivos. Downgrade testado no banco local, ida e volta, inclusive com uma versão gravada com motivos do corpus.
- **Teto com ciclo de 2 meses (desvio)**: com piso 30 dias + ciclo 2 = teto 3, a quantidade necessária cai exatamente no teto e o `ceil` para unidade inteira passava do teto por frações de unidade. No seed, 16 das 23 sugestões com compra passavam a ter `viola_teto` (11 só por arredondamento) e o critério de fornecedor descartava candidatos por isso. `cabe_no_teto` agora tolera menos de uma unidade acima do teto (`estoque_na_chegada + quantidade < giro * teto + 1`). Só o MOQ consegue violar o teto de verdade (1 caso no seed). Teste novo em `test_purchasing.py`.
- **Testes de `purchasing`** ajustados para o ciclo de 2 meses (300 em vez de 200 no exemplo da spec etc.). Os dois testes de MOQ fixam ciclo de 1 mês, porque com o ciclo no limite do teto não sobra espaço para o MOQ arredondar sem violar o teto. Teste novo: `MotivoAlerta` = `TipoAlerta` + `abaixo_do_piso_alerta`.
- **Política na UI**: a seção de faixas saiu e a da fila virou a pergunta 10, "O que faz um produto aparecer no painel de alertas?", com uma caixa por motivo de alerta. As perguntas só leitura passaram a 11 a 15.
- **Home provisória**: `index.html` com links para o chat e a política (o ticket 02 a troca pelo painel).
- **Typecheck**: o repo não tem typecheck configurado. Rodei `uvx pyright --pythonpath .venv/bin/python src tests scripts` e comparei com o HEAD: nenhum erro novo (78 no HEAD, todos antigos; 71 agora).
- `uv run pytest -q` com Postgres: 681 passando, 30 smoke, nenhum pulado.
