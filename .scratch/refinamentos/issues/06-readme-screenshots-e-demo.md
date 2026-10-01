# 06: README final, screenshots, roteiro de demo e fechamento do M8

**Status:** ready-for-agent
**Blocked by:** 01, 02, 03, 04, 05
**Spec:** `.scratch/refinamentos/spec.md` (seção "README final e demo")

## What to build

Fecha o M8 e o MVP: o README vira a porta de entrada do portfólio, com arquitetura e fluxos em mermaid, screenshots da UI tiradas com o Chrome headless e os limites conhecidos atualizados com os números finais. O roteiro de demo em `docs/demo.md` substitui o vídeo, e o roadmap marca o M8 como concluído.

Leia antes os comentários dos tickets 01 a 05 deste milestone (números finais, desvios) e o README inteiro.

Arquivos: `README.md`, `docs/demo.md` (novo), `docs/img/*.png` (novos), `.scratch/copilot-compras/roadmap.md`.

## Acceptance criteria

- [ ] Rodada final dos casos com o redator configurado (`uv run python -m scripts.rodar_casos_chat --respostas --pausa 30`, e `--casos evals/casos_redator.json`), com o resumo (intenção, faixas, ações, vereditos, as três contagens do ticket 02, latência da redação) num comentário deste ticket.
- [ ] README: topo com o resumo do MVP (M0-M8) e o link para `docs/demo.md`; grafo de módulos em `flowchart` mermaid com os serviços externos (Jev, Claude, Groq, Postgres), mantendo a lista de dependências; `sequenceDiagram` do chat e da aprovação; screenshots da fila e do onboarding da política; variáveis `REDATOR`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` e `GROQ_REASONING_EFFORT`; o marcador `externo_llm` com o provedor; limiares novos onde o README cita valores; "Limites conhecidos" com os números finais e o que o M8 resolveu ou não.
- [ ] Screenshots em `docs/img/` tiradas com o comando da spec (Chrome headless, `--window-size=1280,900`, `--virtual-time-budget`), com o app contra o seed, o corpus ingerido e a fila gerada; cada imagem conferida abrindo o arquivo (sem tela vazia ou carregando).
- [ ] `docs/demo.md` com pré-requisitos, preparação e 6 a 8 passos (comando ou tela, o que mostrar, o que esperar), cobrindo o que a spec lista, com duração alvo de 5 a 8 minutos e as screenshots referenciadas. Cada comando do roteiro executado uma vez contra o ambiente local.
- [ ] Os diagramas mermaid conferidos (sintaxe válida, por exemplo com `npx @mermaid-js/mermaid-cli` ou no preview do GitHub depois do push, se não houver ferramenta local; registrar como foi conferido).
- [ ] Roadmap: M8 concluído, com a data e os desvios.
- [ ] `uv run pytest -q` verde (com as chaves que existirem no `.env`).

## Fora do escopo

- Vídeo de demo, deploy, domínio público.
- Mudar código de `src/` ou a UI para facilitar as screenshots (o chat aparece pelo exemplo em texto).
- Novas medidas ou limiares além da rodada final.

## Comments
