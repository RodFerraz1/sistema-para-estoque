# Corpus - Documentos sintéticos

Corpus sintético de partida pro RAG do Copilot de Compras. Tudo aqui é **fictício**: fornecedores, contratos, reuniões, relatórios. Nomes de empresas foram inventados de propósito pra não colidir com empresas reais.

## Estrutura

- `fornecedores/`: fichas de fornecedores (dados mestres + condições comerciais)
- `contratos/`: contratos-modelo com cláusulas de fornecimento
- `reunioes/`: notas de reuniões de compras com decisões e justificativas
- `mercado/`: relatórios de mercado (commodities, tendências)
- `politicas/`: políticas internas de compras

## Tensão deliberada

Os documentos foram escritos com **contradições intencionais** entre si, pra que o RAG realmente ajude na síntese:

- A política de estoque diz "nunca mais que 3 meses de giro". A reunião de novembro/2024 mostra que compraram 5 meses de king size pro Natal e deu certo. A reunião de julho/2024 mostra outro caso onde estocaram além do giro e ficou parado.
- A ficha do fornecedor Katrina promete lead time de 45 dias. A reunião do Q1/2025 questiona esse número (ficou 68 dias na média real).
- O relatório de mercado sugere alta do algodão. A política diz "priorizar fornecedores com preço fechado por 6 meses" - mas o principal fornecedor só oferece 3 meses.

Isso é o ponto: perguntas reais ("compro 500 lençóis king agora?") só têm resposta boa se a IA sintetizar múltiplos documentos.

## Como estender

Adicione mais arquivos livremente. Convenção:

- Um documento por arquivo `.md`.
- Frontmatter YAML com `tipo`, `data` e `tags` pra facilitar filtro no retrieval depois:

```yaml
---
tipo: reuniao
data: 2025-03-14
tags: [fornecedores, sazonalidade]
---
```

## Formato

Markdown puro. Sem PDF/DOCX de propósito: chunking e embedding de markdown é o caminho mais direto. Preprocessamento de formatos exóticos é outra caixinha de complexidade que não interessa agora.
