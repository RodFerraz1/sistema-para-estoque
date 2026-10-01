# Política de compra configurável: mecanismo fixo, parâmetros do comprador

Status: accepted (2026-09-25)

A sugestão de pedido (`purchasing`) separa duas coisas:

1. **Mecanismo**, fixo no código: o que é corretude e vale para qualquer comprador. A posição inclui o que está em trânsito, o consumo durante o lead time é descontado, o MOQ é respeitado, a sugestão sempre existe (quantidade 0 com motivo quando não há compra) e uma violação de teto vira alerta, nunca é escondida.
2. **Política de compra**, parâmetros do comprador: teto, pisos, ciclo de compra, qual lead time usar, critério de fornecedor, tratamento de sazonalidade, regra de SKU novo. É um objeto tipado com campos fechados e validação, versionado no schema `copilot` e editável via API. A v1 usa os valores da política v3 do corpus.

Escolhemos isso porque estratégia de compra é decisão do comprador, e o desenvolvedor não domina estoque. Fixar os números no código faria o sistema carregar a opinião de quem programou. Por outro lado, deixar o mecanismo configurável abriria espaço para configurações que compram duas vezes a mesma mercadoria.

A política gravada é a fonte da verdade do cálculo. O documento `politicas/estoque-e-giro.md` do corpus vira contexto histórico para o RAG. Pela ADR-0002, o Jev não extrai números, então não há sincronização automática entre os dois.

## Considered Options

- **Números fixos no código (plano original do roadmap)**: rejeitada. Embute a estratégia do dev e exige deploy para cada ajuste.
- **Motor de regras genérico, com o comprador escrevendo as próprias regras**: rejeitada. É um produto inteiro (inner-platform effect), difícil de validar e de explicar, e deixa o comprador configurar coisas que quebram a corretude.
- **Política em arquivo de config ou variável de ambiente**: rejeitada. Mudar a política exigiria redeploy, e o onboarding precisa gravar pela aplicação.

## Consequences

- Toda regra nova de estratégia exige decidir se é mecanismo ou parâmetro. Parâmetro novo significa migration (coluna tipada) e valor padrão.
- Cada sugestão informa a `politica_versao` usada. O M7 vai precisar disso para auditar aprovações.
- A tela de onboarding (M7) é só uma interface que preenche a política. Não muda o motor.
- Os parâmetros sem base na política v3 começam como chutes, até o comprador responder `.scratch/sugestao-compra/perguntas-comprador.md`.
- Um atacadista só. Multi-tenant exigiria uma política por tenant e outra ADR.
