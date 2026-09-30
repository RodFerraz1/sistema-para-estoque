from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from src.ai.busca import BuscaContexto
from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.embeddings import Embedder, FastEmbedEmbedder
from src.ai.jev import JevDecisionModel, criar_cliente
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


def get_decision_model() -> DecisionModel:
    settings = get_settings()
    if not settings.jev_key:
        raise DecisaoIndisponivel("JEV_KEY não configurada")
    return _jev(settings.jev_key, settings.jev_model)


@lru_cache(maxsize=1)
def _jev(chave: str, modelo: str) -> DecisionModel:
    return JevDecisionModel(criar_cliente(chave, modelo))


def get_busca_contexto(
    embedder: Embedder = Depends(get_embedder),
    repositorio: TrechosRepositorio = Depends(get_trechos_repositorio),
    decisao: DecisionModel = Depends(get_decision_model),
) -> BuscaContexto:
    return BuscaContexto(embedder, repositorio, decisao)
