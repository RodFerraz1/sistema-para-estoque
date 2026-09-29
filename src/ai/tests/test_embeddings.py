"""Testes do `FastEmbedEmbedder` com o `TextEmbedding` do fastembed substituído,
para não baixar modelo. O modelo real é exercitado pelo smoke e pelos scripts.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.ai import embeddings
from src.ai.embeddings import DIMENSAO, DimensaoIncompativel, FastEmbedEmbedder


class TextEmbeddingFalso:
    def __init__(self, dimensao: int):
        self.embedding_size = dimensao
        self.argumentos: dict[str, str] = {}

    def __call__(self, model_name: str, cache_dir: str) -> TextEmbeddingFalso:
        self.argumentos = {"model_name": model_name, "cache_dir": cache_dir}
        return self

    def embed(self, textos: list[str]):
        for texto in textos:
            yield np.full(self.embedding_size, len(texto), dtype=np.float32)


def test_carrega_o_modelo_configurado_no_cache_configurado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    falso = TextEmbeddingFalso(DIMENSAO)
    monkeypatch.setattr(embeddings, "TextEmbedding", falso)

    embedder = FastEmbedEmbedder("modelo/x", Path("/tmp/cache"))

    assert falso.argumentos == {"model_name": "modelo/x", "cache_dir": "/tmp/cache"}
    assert embedder.dimensao == DIMENSAO


def test_embed_devolve_listas_de_float(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings, "TextEmbedding", TextEmbeddingFalso(DIMENSAO))

    vetores = FastEmbedEmbedder("modelo/x", Path("/tmp/cache")).embed(["ab", "abc"])

    assert [type(v) for v in vetores] == [list, list]
    assert [v[0] for v in vetores] == [2.0, 3.0]
    assert all(len(v) == DIMENSAO for v in vetores)


def test_modelo_com_dimensao_diferente_de_384_falha_na_inicializacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(embeddings, "TextEmbedding", TextEmbeddingFalso(768))

    with pytest.raises(DimensaoIncompativel, match="768"):
        FastEmbedEmbedder("modelo/grande", Path("/tmp/cache"))
