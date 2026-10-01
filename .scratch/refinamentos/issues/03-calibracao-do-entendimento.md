# 03: Calibração do entendimento (relatório do registro, intenção e faixas)

**Status:** ready-for-agent
**Blocked by:** 04
**Spec:** `.scratch/refinamentos/spec.md` (seções "Calibração do entendimento" e "Regra de calibração")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O registro de decisão passa a servir à calibração: um relatório sobre `copilot.registros_decisao` e uma exportação das perguntas para rotular às cegas, porque a tabela não tem rótulo de acerto. Com um conjunto novo de perguntas de validação, a `Choice` de intenção ganha critérios estruturados onde o spike errou (c11, "Qual o lead time de verdade da Katrina?", `situacao_sku` com 0,31 a 0,49 em quatro medições), e as faixas e o `LIMIAR_PRODUTO` são revistos pela regra do ticket 04. Com pouco dado, a decisão é manter, e ela fica registrada.

Antes de mexer na pergunta, invoque a skill `typesafe:typesafe-ai` e leia https://docs.typesafe.ai/primitives/choice.md (critérios estruturados) e https://docs.typesafe.ai/confidence.md. Leia também os comentários de `.scratch/chat/issues/01-entendimento-da-pergunta.md` e `.scratch/chat/issues/05-readme-e-smoke.md`.

Arquivos: `scripts/relatorio_registros.py` (novo), `scripts/avaliar_entendimento.py`, `evals/intencoes.json` (novo), `src/ai/jev.py` (só `PERGUNTA_INTENCAO` e a docstring), `src/ai/chat.py` (só `FAIXAS` e o comentário de `FaixasConfianca`), `src/ai/identificacao.py` (só `LIMIAR_PRODUTO`, se a regra mandar), `src/ai/tests/test_evals.py`, `tests/test_avaliar_entendimento.py`, `tests/test_relatorio_registros.py` (novo) e os testes do `JevDecisionModel` que conferem a pergunta.

## Acceptance criteria

- [ ] `scripts/relatorio_registros.py` com o relatório da spec (totais, perguntas distintas, confiança por intenção, faixas, ações, perguntas medidas mais de uma vez com a dispersão, redator, durações, vereditos perto do limiar, sinais) e `--exportar ARQ` (perguntas distintas fora de `casos.json` e de `intencoes.json`, sem a resposta do Jev). Contas em funções puras testadas com registros em memória.
- [ ] Relatório rodado contra o banco local, com o resumo num comentário deste ticket.
- [ ] `evals/intencoes.json` com pelo menos 12 perguntas escritas à mão (pelo menos 3 por intenção e 4 na fronteira entre `situacao_sku` e `politica_ou_fornecedor`) mais as exportadas do registro, rotuladas antes de rodar e sem repetir `casos.json`. `test_evals.py` confere ids únicos, as quatro intenções, a ausência de repetição e os produtos do catálogo do seed.
- [ ] `avaliar_entendimento.py` com `--casos` (um ou mais arquivos), `--rotulo` no nome do resultado, acerto por arquivo e a regra de calibração no produto e nas faixas.
- [ ] Medida de base (`--rotulo antes`) com a pergunta atual nos dois arquivos, critérios estruturados em `PERGUNTA_INTENCAO` (exemplos sem repetir perguntas dos evals) e medida nova (`--rotulo depois`). A pergunta nova fica só se cumprir as três condições da spec; senão, volta a antiga. Respostas cruas em `evals/resultados/`.
- [ ] `FAIXAS` e `LIMIAR_PRODUTO` pela regra da spec com a medida que ficou valendo. Se a amostra não bastar, os valores ficam e o motivo vai no comentário de `FaixasConfianca` (e de `LIMIAR_PRODUTO`, se for o caso) e neste ticket.
- [ ] Comentário deste ticket com: o resumo do relatório, a pergunta antes e depois, o acerto e as confianças dos erros nas duas medidas (com o c11 destacado), a decisão sobre a pergunta e a saída da regra para as faixas e o produto.
- [ ] `uv run pytest -q -m "not externo and not externo_llm"` verde e os `externo` do entendimento passando.

## Fora do escopo

- Mudar a pergunta do produto ou a identificação dos SKUs.
- Gravar rótulos no banco ou criar tela de rotulagem.
- Conflito entre trechos (ticket 05) e limiares dos sinais e da citação (ticket 04).
- Atualizar o README (ticket 06).

## Comments
