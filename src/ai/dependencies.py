from __future__ import annotations

from functools import lru_cache

from src.ai.embeddings import Embedder, FastEmbedEmbedder
from src.ai.postgres import PostgresTrechosRepositorio
from src.ai.repositorio import TrechosRepositorio
from src.db.config import get_settings
from src.db.engine import get_engine


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    settings = get_settings()
    return FastEmbedEmbedder(settings.embedding_model, settings.fastembed_cache_path)


def get_trechos_repositorio() -> TrechosRepositorio:
    return PostgresTrechosRepositorio(get_engine())
