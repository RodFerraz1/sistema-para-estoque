"""Port do modelo de embedding e o adapter local com fastembed (ADR-0004)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

# O onnxruntime do fastembed manda telemetria em segundo plano, e um envio em andamento
# na saída do processo aborta o Python (SIGABRT). Só vale se definida antes do import.
os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")

from fastembed import TextEmbedding  # noqa: E402

DIMENSAO = 384


class Embedder(Protocol):
    dimensao: int

    def embed(self, textos: list[str]) -> list[list[float]]: ...


class DimensaoIncompativel(ValueError):
    pass


class FastEmbedEmbedder:
    def __init__(self, modelo: str, cache: Path) -> None:
        self._modelo = TextEmbedding(model_name=modelo, cache_dir=str(cache))
        self.dimensao = self._modelo.embedding_size
        if self.dimensao != DIMENSAO:
            raise DimensaoIncompativel(
                f"{modelo} gera vetores de {self.dimensao} dimensões, "
                f"a coluna copilot.trechos_corpus.embedding tem {DIMENSAO}"
            )

    def embed(self, textos: list[str]) -> list[list[float]]:
        return [vetor.tolist() for vetor in self._modelo.embed(textos)]
