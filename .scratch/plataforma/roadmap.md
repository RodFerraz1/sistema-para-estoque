# Roadmap - depois da spec 09

O que a reunião de 2026-10-03 com o comprador chefe trouxe e ficou fora de `spec.md`, em ordem de dependência. Nada aqui tem ticket: cada item vira spec própria quando a dependência for resolvida.

## Depende da integração com o Maos

- **Similar.** Botão na tela da vendedora que mostra o produto semelhante ao que está faltando, para oferecer ao cliente. O Maos já tem essa função. Entra como `similares_de(sku)` na porta do ERP. Enquanto isso, o Substituto (mesma categoria e tamanho) atende o comprador na negociação. Ele não é oferecido à vendedora, para não confundir os dois conceitos.
- **Histórico de 5 anos.** O ERP fake tem 24 meses sintéticos.
- **Estoque por local** (depósito e loja). Com ele, a gôndola vazia aparece direto, sem precisar da heurística de queda de venda.
- **Criar pedido de compra e ajustar estoque** no ERP real, depois da decisão de compra (ADR-0005).

## Depende de dados

- **Sazonalidade e volatilidade com machine learning.** Modelo por SKU (ou por categoria, para SKU com pouco histórico) treinado em 5 anos de vendas, que entrega uma venda média diária prevista para os próximos dias. Ela substitui a média dos últimos 6 meses no cálculo da cobertura em dias. O exemplo do comprador: edredom vende no frio e não no verão. Pede uma ADR própria, porque o modelo vira parte do mecanismo (ADR-0003).
- **Lead time real por fornecedor**, aprendido das entregas (data prevista contra data recebida). O histórico de atrasos da spec 09 é o começo. Quando ficar confiável, a política pode voltar de `ignorar` para `observado` (ADR-0006).
- **Calibração da queda de venda** com as verificações `estava_na_gondola` (alarme falso) da primeira semana de uso.

## Depende de decisão do comprador

- **Dados que faltam para a vendedora e para o comprador**, que a reunião citou sem detalhar. Ver o item 6 dos pormenores em `spec.md`.
- **Dias de segurança por categoria ou por SKU**, se a regra única da política não servir.
- **Demanda não atendida**: registrar o que o cliente pediu e não tinha, separado do aviso `acabou`.

## Depende de infraestrutura

- **Notificação fora do Copilot** (WhatsApp, e-mail, push) e o agendador em segundo plano que roda a varredura sem ninguém com o Copilot aberto.
- **Deploy** com HTTPS (o cookie de sessão exige `Secure` fora do ambiente local), backup do schema `copilot` e logs.
