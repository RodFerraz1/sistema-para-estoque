# 02: Fila de aprovação

**Status:** ready-for-agent
**Blocked by:** 01
**Spec:** `.scratch/aprovacao/spec.md` (seção "Fila de aprovação")

## What to build

Módulo `aprovacao`: gera sugestões para todos os SKUs ativos, guarda as com quantidade na fila com sinais do corpus e faixa, ordena com destaque para quem tem alerta, e registra a decisão humana. Aprovar cria o pedido no ERP; rejeitar exige motivo.

## Acceptance criteria

- [ ] Migration `0007` com `copilot.sugestoes_fila` e o índice da spec.
- [ ] `src/aprovacao/`: DTOs (`SugestaoNaFila`, `ResultadoGeracao`), port do repositório com Postgres e in-memory (teste de contrato), serviço `Aprovacao` (`gerar_fila`, `listar`, `carregar`, `aprovar`, `rejeitar`) e exceções (`SugestaoJaDecidida`, `JustificativaObrigatoria`, quantidade abaixo do MOQ).
- [ ] Endpoints de `src/api/aprovacao.py` com os códigos da spec, router registrado.
- [ ] Testes da spec (serviço com adapters em memória, contrato, HTTP).
- [ ] `uv run pytest -q -m "not externo"` verde.

## Comments
