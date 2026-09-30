# 01: Corpus em `corpus/` e leitura em trechos

**Status:** done
**Blocked by:** None (can start immediately)
**Spec:** `.scratch/rag-jev/spec.md`

## What to build

O corpus sai de `.scratch/copilot-compras/rag-seeds/` e vai para `corpus/` na raiz, para entrar na imagem Docker. Nasce o módulo `src/ai/` com o leitor `ler_corpus(pasta) -> list[Trecho]`, uma função pura que quebra cada documento em trechos por seção, com metadados do frontmatter e id estável. É a base dos rótulos do spike (02) e da ingestão (03).

## Acceptance criteria

- [x] `git mv .scratch/copilot-compras/rag-seeds corpus`. Referências a `rag-seeds` no repositório (`CONTEXT.md`, roadmap, specs, `README.md` do corpus) apontam para `corpus/`.
- [x] `src/ai/schemas.py` com `Trecho` (`id`, `documento`, `titulo`, `tipo`, `data`, `tags`, `texto`), Pydantic frozen.
- [x] `src/ai/corpus.py` com `ler_corpus(pasta: Path) -> list[Trecho]`, seguindo as regras da spec: um trecho por `##`/`###`, texto antes do primeiro `##` vira trecho quando tem conteúdo, seção só com título não vira trecho, `titulo` como caminho de títulos, `texto` com título e corpo, id `<documento>#<slug>` com sufixo em colisão, quebra por parágrafo acima de 300 palavras, `README.md` ignorado.
- [x] Documento sem frontmatter ou com `data` inválida lança erro com o nome do arquivo.
- [x] `pyyaml` declarada no `pyproject.toml`.
- [x] Testes unitários com markdown de fixture cobrindo cada regra, e um teste que lê o `corpus/` real e confere que os ids são únicos e que todo documento gera pelo menos um trecho.
- [x] `uv run pytest` verde.
