# Arquiteturas candidatas para o Copilot de Compras

Documento de decisão. Escolha uma, aí ADRzamos em `docs/adr/`.

## Pré-requisitos que já não estão em jogo

- É um **modular monolith** (um processo, um deploy, mas com fronteiras internas).
- Depois vai migrar partes pra microserviço quando doer.
- Python + FastAPI + Postgres + pgvector.
- Ports & Adapters é premissa: qualquer coisa externa (ERP, LLM, vector search) fica atrás de uma interface.

A pergunta aberta é: **como organizamos o código dentro do monolito?** Existem 4 formas honestas de fazer isso. Cada uma tem um tradeoff diferente entre "aprendo arquitetura" e "avanço rápido".

---

## Opção A - Monolito modular por domínio (a minha proposta)

```
src/
├── catalog/          # SKUs, categorias, fornecedores
├── inventory/        # estoque, movimentações
├── sales/            # histórico de vendas, previsões
├── purchasing/       # pedidos de compra, aprovações
├── ai/               # RAG, orquestração de LLM, tool calls
├── erp_adapter/      # única camada que fala com ERP (fake ou real)
└── api/              # camada HTTP que amarra tudo
```

Cada módulo é um pequeno subsistema com seu próprio modelo, regras e interface pública. Módulos NÃO acessam banco uns dos outros direto - falam por interfaces.

**Por que essa é a proposta padrão pra aprender arquitetura:**

- É a forma que a *indústria* organiza sistemas grandes hoje (Domain-Driven Design "light").
- Cada módulo é um candidato direto a virar microserviço. Você vai *sentir* quando quebrar.
- Te força a pensar em fronteiras cedo, que é o skill que você quer aprender.

**Custo:**

- Curva mais íngreme no começo. Você vai errar as fronteiras e ter que mexer.
- Mais boilerplate (interfaces, DTOs entre módulos).
- Pra CRUD simples parece exagero. Mas seu domínio não é CRUD simples.

**Quando é a escolha errada:** projeto pequeno, curto, ou onde a lógica de negócio é fina. Não é seu caso.

---

## Opção B - Arquitetura em camadas (N-tier / MVC clássico)

```
src/
├── controllers/      # endpoints HTTP
├── services/         # lógica de negócio
├── repositories/     # acesso a banco
├── models/           # entidades
└── ai/               # tudo de AI aqui
```

O que quase todo tutorial de FastAPI/Django/Rails mostra. Você organiza por *tipo técnico* de coisa (controller, service, repository), não por conceito de negócio.

**O que ensina bem:**

- Separação básica de responsabilidades (HTTP não é lógica, lógica não é banco).
- Fácil de começar. Zero decisão inicial.

**Por que NÃO é a melhor pro seu caso:**

- **Não escala**: com o tempo, `services/` vira uma pasta com 40 arquivos onde `purchasing_service.py` importa `inventory_service.py` importa `sales_service.py` importa `purchasing_service.py` de volta. Acopla tudo em tudo.
- **Não te ensina fronteiras**: você aprende a separar HTTP de lógica, mas *não* aprende a modelar domínio - que é o skill de arquitetura que você quer.
- **Migração pra microserviço é dor**: as fronteiras não existem no código, então quebrar em serviços é reescrever.

**Quando faz sentido:** CRUD linear, equipe pequena, prazo curto, domínio raso. Novamente, não é seu caso.

---

## Opção C - Arquitetura hexagonal pura (Clean Architecture)

```
src/
├── domain/           # entidades e regras puras (sem framework)
├── application/      # casos de uso (orquestração)
├── infrastructure/   # postgres, http externos, LLM, ERP
└── interfaces/       # HTTP, CLI, jobs
```

Versão *disciplinada* de Ports & Adapters. Domain no centro, tudo apontando pra dentro. Nenhum código de domínio importa framework.

**O que ensina bem:**

- Testabilidade extrema (domain roda sem banco, sem HTTP, sem nada).
- Disciplina de dependências: nada de infra vaza pra domain.
- É *o* estilo que Uncle Bob e a galera de DDD ensinam.

**Por que provavelmente NÃO agora:**

- **Overkill pro seu momento**: muita cerimônia (mappers entre domain/DTO, casos de uso pra tudo, portas pra tudo). Você vai gastar mais tempo com ceremony do que com problema real.
- **Não é ortogonal à A**: dá pra combinar - cada módulo da Opção A pode internamente ser hexagonal quando precisar. Você não precisa escolher tudo desde o dia 1.

**Quando faz sentido:** quando o domínio é complexo *dentro* de um módulo específico (ex: engine de sugestão de compra, dentro de `ai/`, pode ser hexagonal). Uso *pontual*, não como estrutura geral do projeto.

---

## Opção D - Vertical slice (feature-based)

```
src/
├── features/
│   ├── sugerir_compra/     # tudo desta feature: http, lógica, banco
│   ├── aprovar_pedido/     # tudo desta feature
│   └── ingestar_documentos/
└── shared/                 # o que é genuinamente compartilhado
```

Organiza por *caso de uso* (feature) e não por domínio nem por camada. Cada slice é auto-contido.

**O que ensina bem:**

- Alto foco: você trabalha uma feature por vez, sem ficar navegando 5 pastas.
- Popular em CQRS e times ágeis pequenos.

**Por que NÃO agora:**

- **Duplica conceitos de domínio**: `sugerir_compra/estoque.py` e `aprovar_pedido/estoque.py` viram duas leituras do conceito "estoque". Você quer aprender o *oposto* disso: consolidar domínio.
- **Não te ensina fronteiras de domínio**: te ensina fronteiras de feature, que é outra coisa (e menos requisitada em job description).

**Quando faz sentido:** apps com features muito independentes (dashboard de N ferramentas), ou times que rodam em CQRS. Não é seu caso.

---

## Recomendação

**Opção A** com Ports & Adapters localizado dentro do módulo `erp_adapter` e `ai` (que precisam mesmo isolar coisas externas). Não força hexagonal no resto.

Justificativa:
1. Você quer aprender arquitetura de verdade. A é a única que te obriga a pensar em fronteiras de domínio - o skill central.
2. É a única que faz o path "monolito → microserviço" ser suave.
3. Ports & Adapters entra onde precisa (adapter de ERP e adapter de LLM), não como cerimônia global.

## Decisão

_Preencher depois:_

- Opção escolhida:
- Data:
- Motivo curto:
