# Monolito modular organizado por domínio

Status: accepted (2026-09-16)

O Copilot de Compras vai ser um monolito modular organizado por conceitos de domínio (`catalog`, `inventory`, `sales`, `purchasing`, `ai`, `erp_adapter`), e não por camada técnica (controllers/services/repositories) nem por vertical slice de feature. Escolhemos isso porque o objetivo do projeto é aprender arquitetura de software na prática, e essa organização é a única entre as candidatas que força fronteiras de domínio explícitas desde cedo e prepara o caminho pra migrar módulos pra microserviços quando o custo de acoplamento aparecer.

## Considered Options

Análise completa em `.scratch/copilot-compras/architecture-options.md`. Resumo dos rejeitados:

- **B - Camadas (N-tier / MVC)**: rejeitada porque organiza por tipo técnico e não ensina modelagem de domínio, que é o skill central do projeto. Também dificulta migração posterior pra serviços.
- **C - Hexagonal pura (Clean Architecture)**: rejeitada como estrutura geral por excesso de cerimônia inicial. Reaproveitada pontualmente: os módulos `erp_adapter` e `ai` internamente seguem Ports & Adapters porque isolam dependências externas voláteis.
- **D - Vertical slice / feature-based**: rejeitada porque duplica conceitos de domínio entre features e ensina fronteira errada pro portfólio pretendido (AI engineer).

## Consequences

- Comunicação entre módulos passa por interfaces internas explícitas, não por acesso direto a tabelas de outro módulo. Isso vai gerar boilerplate no começo (DTOs, interfaces) que é *intencional* - a fricção é o sinal pra decidir quando quebrar em serviço.
- Módulo `erp_adapter` é a única fronteira que fala com o ERP fake. Trocar o ERP fake por um real no futuro (Ports & Adapters) muda apenas a implementação desse módulo.
- Módulo `ai` isola LLM, RAG e orquestração de agente. Trocar Groq por Claude/Ollama muda só uma implementação.
- A migração planejada pra microserviços vai ser feita módulo a módulo, começando pelo que sentir dor primeiro (candidato mais provável: `ai`, por ter perfil de escala e dependências externas diferentes do resto).
