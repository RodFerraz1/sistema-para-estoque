# Jev decide, código executa, LLM redige

Status: accepted (2026-09-25)

O módulo `ai` deixa de ser "LLM com tool use" e passa a ter três papéis separados:

1. **Jev (TypeSafe, System One)** toma as decisões semânticas estreitas: qual é a intenção da pergunta, qual tool chamar, se um trecho do corpus é relevante, se contradiz outro, se tem tentativa de injeção, se uma citação bate com o documento e que sinais qualitativos o corpus traz sobre um fornecedor ou uma época do ano. Toda decisão é uma pergunta tipada (`Choice`, `Score`, `Noul`) e volta com probabilidades e confiança.
2. **Código** controla o fluxo: roteia pela resposta do Jev, chama `catalog`, `inventory`, `sales` e `purchasing`, aplica thresholds de confiança e faz toda conta (giro, cobertura, quantidade, datas).
3. **LLM** só redige a resposta final em linguagem natural a partir de dados que o código já montou. Não escolhe tools nem decide nada.

Escolhemos isso porque a hipótese é que decisões tipadas e calibradas são mais precisas, baratas, rápidas e testáveis do que deixar o LLM decidir em texto livre. Além disso, a confiança dá um segundo eixo para o human-in-the-loop.

## Considered Options

- **LLM com tool use (plano original do roadmap)**: rejeitada. Decisão e geração ficam misturadas numa chamada opaca, sem confiança calibrada e com resposta difícil de testar.
- **Jev sem LLM (tela estruturada com explicação por template)**: rejeitada. Elimina o chat em linguagem livre, que é premissa do Copilot.

## Consequences

- O Jev entra atrás de um port no `ai` (Ports & Adapters, como previsto na ADR-0001), com um adapter in-memory para os testes. O LLM continua atrás do seu próprio port e trocar Groq por Claude/GPT afeta só o redator.
- A divisão por risco de `module-interfaces.md` continua valendo: o Jev só roteia para leitura e para `purchasing.sugerir_pedido`, e ações irreversíveis seguem exclusivas da aprovação humana.
- Números, contagens e comparações de datas nunca vão para o Jev. A doc do Jev 1.13 aponta essas tarefas como fraquezas conhecidas.
- Passamos a depender de dois fornecedores de IA.
- **Condição de revisão**: o spike do início do M4 precisa mostrar que o Jev funciona em português com o corpus e as perguntas do comprador, com custo e latência aceitáveis. Se falhar, esta ADR é substituída e o `ai` volta ao tool use via LLM.
