from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from src.ai.busca import BuscaContexto
from src.ai.chat import Copilot
from src.ai.decisao import DecisaoIndisponivel, DecisionModel
from src.ai.embeddings import Embedder, FastEmbedEmbedder
from src.ai.groq import GroqRedator
from src.ai.jev import JevDecisionModel, criar_cliente
from src.ai.postgres import PostgresRegistrosDecisao, PostgresTrechosRepositorio
from src.ai.redator import Redator, RedatorSemLLM
from src.ai.registro import RegistrosDecisao
from src.ai.repositorio import TrechosRepositorio
from src.ai.sinais import SinaisCorpus
from src.catalog.dependencies import get_catalog
from src.catalog.service import Catalog
from src.db.config import get_settings
from src.db.engine import get_engine
from src.ficha_sku.dependencies import get_ficha_sku
from src.ficha_sku.service import FichaSKU
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.purchasing.dependencies import get_purchasing
from src.purchasing.service import Purchasing


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    settings = get_settings()
    return FastEmbedEmbedder(settings.embedding_model, settings.fastembed_cache_path)


def get_trechos_repositorio() -> TrechosRepositorio:
    return PostgresTrechosRepositorio(get_engine())


def get_registros_decisao() -> RegistrosDecisao:
    return PostgresRegistrosDecisao(get_engine())


def get_decision_model() -> DecisionModel:
    settings = get_settings()
    if not settings.jev_key:
        raise DecisaoIndisponivel("JEV_KEY não configurada")
    return _jev(settings.jev_key, settings.jev_model)


@lru_cache(maxsize=1)
def _jev(chave: str, modelo: str) -> DecisionModel:
    return JevDecisionModel(criar_cliente(chave, modelo))


def get_redator() -> Redator:
    settings = get_settings()
    if not settings.groq_api_key:
        return RedatorSemLLM()
    return _groq(settings.groq_api_key, settings.groq_model, settings.groq_base_url)


@lru_cache(maxsize=1)
def _groq(chave: str, modelo: str, base_url: str) -> Redator:
    return GroqRedator(chave, modelo, base_url)


def get_busca_contexto(
    embedder: Embedder = Depends(get_embedder),
    repositorio: TrechosRepositorio = Depends(get_trechos_repositorio),
    decisao: DecisionModel = Depends(get_decision_model),
) -> BuscaContexto:
    return BuscaContexto(embedder, repositorio, decisao)


def get_sinais_corpus(
    busca: BuscaContexto = Depends(get_busca_contexto),
    decisao: DecisionModel = Depends(get_decision_model),
) -> SinaisCorpus:
    return SinaisCorpus(busca, decisao)


def get_copilot(
    decisao: DecisionModel = Depends(get_decision_model),
    catalog: Catalog = Depends(get_catalog),
    ficha_sku: FichaSKU = Depends(get_ficha_sku),
    purchasing: Purchasing = Depends(get_purchasing),
    politicas: PoliticaCompraRepositorio = Depends(get_politica_compra_repositorio),
    busca: BuscaContexto = Depends(get_busca_contexto),
    redator: Redator = Depends(get_redator),
    registros: RegistrosDecisao = Depends(get_registros_decisao),
) -> Copilot:
    return Copilot(decisao, catalog, ficha_sku, purchasing, politicas, busca, redator, registros)
