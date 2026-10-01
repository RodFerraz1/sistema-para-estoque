# 03: Calibração do entendimento (relatório do registro, intenção e faixas)

**Status:** done
**Blocked by:** 04
**Spec:** `.scratch/refinamentos/spec.md` (seções "Calibração do entendimento" e "Regra de calibração")
**ADR:** `docs/adr/0002-jev-decide-codigo-executa-llm-redige.md`

## What to build

O registro de decisão passa a servir à calibração: um relatório sobre `copilot.registros_decisao` e uma exportação das perguntas para rotular às cegas, porque a tabela não tem rótulo de acerto. Com um conjunto novo de perguntas de validação, a `Choice` de intenção ganha critérios estruturados onde o spike errou (c11, "Qual o lead time de verdade da Katrina?", `situacao_sku` com 0,31 a 0,49 em quatro medições), e as faixas e o `LIMIAR_PRODUTO` são revistos pela regra do ticket 04. Com pouco dado, a decisão é manter, e ela fica registrada.

Antes de mexer na pergunta, invoque a skill `typesafe:typesafe-ai` e leia https://docs.typesafe.ai/primitives/choice.md (critérios estruturados) e https://docs.typesafe.ai/confidence.md. Leia também os comentários de `.scratch/chat/issues/01-entendimento-da-pergunta.md` e `.scratch/chat/issues/05-readme-e-smoke.md`.

Arquivos: `scripts/relatorio_registros.py` (novo), `scripts/avaliar_entendimento.py`, `evals/intencoes.json` (novo), `src/ai/jev.py` (só `PERGUNTA_INTENCAO` e a docstring), `src/ai/chat.py` (só `FAIXAS` e o comentário de `FaixasConfianca`), `src/ai/identificacao.py` (só `LIMIAR_PRODUTO`, se a regra mandar), `src/ai/tests/test_evals.py`, `tests/test_avaliar_entendimento.py`, `tests/test_relatorio_registros.py` (novo) e os testes do `JevDecisionModel` que conferem a pergunta.

## Acceptance criteria

- [x] `scripts/relatorio_registros.py` com o relatório da spec (totais, perguntas distintas, confiança por intenção, faixas, ações, perguntas medidas mais de uma vez com a dispersão, redator, durações, vereditos perto do limiar, sinais) e `--exportar ARQ` (perguntas distintas fora de `casos.json` e de `intencoes.json`, sem a resposta do Jev). Contas em funções puras testadas com registros em memória.
- [x] Relatório rodado contra o banco local, com o resumo num comentário deste ticket.
- [x] `evals/intencoes.json` com pelo menos 12 perguntas escritas à mão (pelo menos 3 por intenção e 4 na fronteira entre `situacao_sku` e `politica_ou_fornecedor`) mais as exportadas do registro, rotuladas antes de rodar e sem repetir `casos.json`. `test_evals.py` confere ids únicos, as quatro intenções, a ausência de repetição e os produtos do catálogo do seed.
- [x] `avaliar_entendimento.py` com `--casos` (um ou mais arquivos), `--rotulo` no nome do resultado, acerto por arquivo e a regra de calibração no produto e nas faixas.
- [x] Medida de base (`--rotulo antes`) com a pergunta atual nos dois arquivos, critérios estruturados em `PERGUNTA_INTENCAO` (exemplos sem repetir perguntas dos evals) e medida nova (`--rotulo depois`). A pergunta nova fica só se cumprir as três condições da spec; senão, volta a antiga. Respostas cruas em `evals/resultados/`.
- [x] `FAIXAS` e `LIMIAR_PRODUTO` pela regra da spec com a medida que ficou valendo. Se a amostra não bastar, os valores ficam e o motivo vai no comentário de `FaixasConfianca` (e de `LIMIAR_PRODUTO`, se for o caso) e neste ticket.
- [x] Comentário deste ticket com: o resumo do relatório, a pergunta antes e depois, o acerto e as confianças dos erros nas duas medidas (com o c11 destacado), a decisão sobre a pergunta e a saída da regra para as faixas e o produto.
- [x] `uv run pytest -q -m "not externo and not externo_llm"` verde e os `externo` do entendimento passando.

## Fora do escopo

- Mudar a pergunta do produto ou a identificação dos SKUs.
- Gravar rótulos no banco ou criar tela de rotulagem.
- Conflito entre trechos (ticket 05) e limiares dos sinais e da citação (ticket 04).
- Atualizar o README (ticket 06).

## Comments

**2026-10-01 (agente):** pronto, com o dev AFK. Decisões, desvios e números:

- **Relatório** (`scripts/relatorio_registros.py`, banco local, antes das rodadas deste ticket): 197 registros de 2026-09-30 19:00 a 2026-10-01 05:44 (UTC), 27 perguntas distintas.
  - Confiança por intenção (quantidade, mínima, mediana, máxima): `situacao_sku` 76, 0,33, 1,00, 1,00; `sugestao_compra` 57, 0,53, 0,97, 1,00; `politica_ou_fornecedor` 29, 0,65, 0,91, 1,00; `fora_de_escopo` 35, todas 1,00.
  - Faixas: alta 168, média 22, baixa 7. Ações: `respondeu` 114, `confirmou_e_respondeu` 22, `pediu_esclarecimento` 26, `fora_de_escopo` 35.
  - Maiores dispersões entre as perguntas repetidas: c11 "Qual o lead time de verdade da Katrina?" 7 vezes, sempre `situacao_sku`, de 0,33 a 0,45; c09 (Katrina em 45 dias) de 0,53 a 0,64; c14 (Verdela atrasando) de 0,65 a 0,74; c02 (cobertura do percal 200 king) de 0,79 a 0,88, cruzando a `alta`; c13 de 0,80 a 0,87. Nenhuma pergunta repetida mudou de intenção entre as medições.
  - Redator: Groq 112, sem redação (resposta em código) 61, `sem_llm` 24. Duração (mediana e p90): `respondeu` 3,96 s e 7,16 s; `confirmou_e_respondeu` 5,67 s e 9,72 s; esclarecimento 0,40 s e 0,43 s; fora de escopo 0,42 s e 0,51 s.
  - Vereditos de citação: 90 `confirmada`, 11 `sem_suporte`, 1 `contradita`, 2 `inventada`, 20 `incerta`; 22 das 122 confianças ficam a menos de 0,10 do `LIMIAR_CITACAO` (0,80). Sinais: 11 de atraso, 11 de encalhe, nenhum de venda por época; 0 de 31 sugestões com sinais nulos.
- **Exportação**: 7 perguntas (r01 a r07): as 4 de `casos_redator.json`, a variante "Quanto devo comprar do TBC-BEGE-70140-01?" (sem "SKU") e duas avulsas ("A Katrina costuma atrasar as entregas?" e "Quanto devo comprar do ED-CINZ-CASAL-03? A Verdela costuma atrasar?"). **Desvio na cegueira**: o relatório lista a intenção das perguntas repetidas e eu inspecionei os registros antes de exportar, então vi a intenção do Jev de r01 a r07. Os rótulos seguem as definições da intenção e o produto do código no seed, sem caso ambíguo, exceto r06 (pergunta dupla), rotulado `sugestao_compra` pela parte com o SKU, que é a que o chat roteia. r04 (`JDCP-BRAN-QUEEN-02`) aceita Percal 200 e 300, porque o prefixo `JDCP` é dos dois produtos.
- **`evals/intencoes.json`**: 25 perguntas, rotuladas antes de rodar: 18 à mão (i01 a i18) e as 7 exportadas. Por intenção: `situacao_sku` 6, `sugestao_compra` 8, `politica_ou_fornecedor` 8, `fora_de_escopo` 3. Fronteira entre `situacao_sku` e `politica_ou_fornecedor`: i04 e i05 (estoque e cobertura de um produto citando o fornecedor) e i09 a i12 (prazo, lead time real, atraso e atraso de um produto). **Desvio de formato**: só `id`, `pergunta`, `intencao` e `produtos_aceitos` (o formato da exportação), sem os campos de trechos de `casos.json`, que a avaliação do entendimento não usa; spec atualizada. `test_evals.py` confere ids únicos (também contra `casos.json`), perguntas únicas, as quatro intenções com pelo menos 3, nenhuma pergunta de `casos.json` (comparadas normalizadas) e os produtos do seed.
- **`avaliar_entendimento.py`**: `--casos` com um ou mais arquivos (recusa id repetido), `--rotulo`, acerto de intenção e produto por arquivo e no total, o resultado grava os arquivos usados e `--de-arquivo` recusa caso sem resposta. A varredura do produto fica só para leitura. `escolher_limiar_produto` e `LIMIAR_SEM_ZERO_ERROS` saíram; no lugar, `calibrar_produto` (erro crítico: produto diferente de `nenhum` fora de `produtos_aceitos`) e `calibrar_faixas` (`media` pela regra sem erro crítico; `alta` pela regra do erro crítico com os erros de intenção de confiança a partir da `alta` atual, então sem esse erro dá `amostra_insuficiente` e ela fica; conflito quando `media >= alta`). Decisão: na contagem "uma vez por pergunta distinta", vale a primeira vez que a pergunta aparece.
- **Pergunta antes**: a do spike, com critério em uma frase por opção. **Depois**: os mesmos `instructions` e critérios estruturados nas quatro opções (`cobre`, `nao_cobre` e `exemplos`), no formato da doc da `Choice`. `politica_ou_fornecedor` cobre a política e tudo sobre um fornecedor (prazo, lead time contratado e real, atrasos, histórico de entregas, contrato, condições, pedido mínimo, reajuste e exclusividade) e diz que estoque, giro e cobertura são de `situacao_sku` mesmo citando o fornecedor; `situacao_sku` diz o contrário. Os 9 exemplos não repetem perguntas dos evals (teste novo em `test_jev.py`).
- **Medidas** (`jev-1.13.0`, 45 requests cada, latência mediana 0,31 s e 0,33 s; `evals/resultados/entendimento-2026-10-01-antes.json` e `-depois.json`):
  - Intenção antes: `casos.json` 19/20, `intencoes.json` 25/25, total 44/45. O único erro é o **c11**: `situacao_sku` com 0,37 (0,52 contra 0,41 de `politica_ou_fornecedor`). Acertos com confiança baixa: i11 ("Os atrasos da Katrina no fim do ano já foram resolvidos?") com 0,17, que iria para esclarecimento, e i12 com 0,55.
  - Intenção depois: 20/20, 25/25, total 45/45. **c11: `politica_ou_fornecedor` com 0,98**. i11 de 0,17 para 0,96, i12 de 0,55 para 1,00, c09 de 0,62 para 0,91, c14 de 0,71 para 0,98, c06 de 0,67 para 0,79; a menor confiança subiu de 0,17 para 0,79. Faixas nas 45 perguntas: de alta 39, média 4 e baixa 2 para alta 44 e média 1 (c06).
  - Erros de intenção: antes um (c11, 0,37); depois nenhum.
  - Produto (pergunta do produto sem mudança): 43/45 nas duas, com os mesmos erros de sempre: c04 `nenhum` (0,66 e 0,67) e c08 Colcha Bouti (0,54 e 0,47). O c09 mudou de Percal 300 com 0,49 para `nenhum` com 0,55, os dois aceitos: é a variação entre medições que o relatório já mostra.
- **Decisão: a pergunta nova fica.** As três condições da spec: c11 certo com 0,98 (>= `FAIXAS.media` 0,50), acerto somado de 44/45 para 45/45 e nenhuma intenção errada com confiança >= 0,80. Teste real novo em `test_jev.py` com o c11 (`politica_ou_fornecedor` com confiança >= `FAIXAS.media`); o teste que conferia a pergunta do spike passou a conferir a gravada em `entendimento-2026-10-01-depois.json`.
- **Regra, com a medida nova**:
  - `FAIXAS.media`: 0,50 (`amostra_insuficiente`; 45 positivos e 0 negativos). `FAIXAS.alta`: 0,80 (`amostra_insuficiente`; 0 erros críticos). Faixas mantidas, com o motivo no comentário de `FaixasConfianca`. Na medida antes daria o mesmo (44 e 1).
  - `LIMIAR_PRODUTO`: 0,60 (`amostra_insuficiente`; 1 erro crítico, o c08 com 0,47). Mantido, com o motivo num comentário da constante. A varredura mostra o erro abaixo de 0,50 e 20 produtos certos usados de 0,50 a 0,55, mas a regra pede 3 erros.
- **Riscos registrados**:
  - Os critérios foram escritos depois de ver a medida de base (é a ordem da spec), e um exemplo ("Quanto tempo a Riva Têxtil leva para entregar na prática?") é parecido em sentido com o c11, sem repetir o texto. As perguntas de fronteira de `intencoes.json` (i09 a i12) e as dos outros fornecedores também subiram, o que sugere que o ganho não é só desse exemplo.
  - Com os critérios novos quase tudo sai com confiança alta: a faixa média (confirmar e responder) quase some nas 45 perguntas, e não há erro na amostra para saber se uma intenção errada também viria com confiança alta. Mais perguntas rotuladas, sobretudo as ambíguas, dariam negativos para a regra.
- **Testes**: `tests/test_relatorio_registros.py` (normalização, confiança por intenção, repetidas com dispersão, duração e p90, vereditos perto do limiar, sinais, exportação e o texto), `tests/test_avaliar_entendimento.py` reescrito (por arquivo, rótulo, ids repetidos, produto e faixas por cada ramo da regra, conflito entre `media` e `alta`), `test_evals.py` e `test_jev.py`. `uv run pytest -q -m "not externo and not externo_llm"` com 830 passando; `-m "not externo"` com 831 passando e 1 pulado (eram 811); `-m "externo and not externo_llm"` com 11 passando, entre eles o teste novo do c11 e o da toalha Conforto branca.
