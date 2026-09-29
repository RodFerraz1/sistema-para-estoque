"""Ingere o corpus de `CORPUS_DIR` em `copilot.trechos_corpus`.

Idempotente: só reprocessa documento novo ou alterado e remove o que sumiu.

    uv run python -m scripts.ingerir_corpus
"""
from __future__ import annotations

from src.ai.dependencies import get_embedder, get_trechos_repositorio
from src.ai.ingestao import ingerir
from src.db.config import get_settings


def main() -> None:
    pasta = get_settings().corpus_dir
    relatorio = ingerir(pasta, get_embedder(), get_trechos_repositorio())
    print(f"corpus: {pasta}")
    for nome in ("novos", "alterados", "removidos"):
        documentos = getattr(relatorio, nome)
        print(f"{nome}: {len(documentos)}")
        for documento in documentos:
            print(f"  {documento}")
    print(f"inalterados: {len(relatorio.inalterados)}")
    print(f"total de trechos: {relatorio.total_trechos}")


if __name__ == "__main__":
    main()
