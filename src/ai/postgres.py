"""Implementação Postgres do `TrechosRepositorio` sobre `copilot.trechos_corpus`.

A similaridade é 1 - distância de cosseno (operador `<=>` do pgvector). Sem
índice vetorial: com poucas centenas de linhas a busca exata é suficiente.
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from src.ai.embeddings import DIMENSAO
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import TrechoIndexado, TrechoRecuperado

_CAMPOS_TRECHO = ("id", "documento", "titulo", "tipo", "data", "tags", "texto")

_INSERT = text(
    "INSERT INTO copilot.trechos_corpus "
    f"({', '.join(_CAMPOS_TRECHO)}, hash_documento, embedding) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_TRECHO)}, :hash_documento, :embedding)"
).bindparams(bindparam("embedding", type_=Vector(DIMENSAO)))

_DELETE = text("DELETE FROM copilot.trechos_corpus WHERE documento = :documento")

_BUSCAR = text(
    f"SELECT {', '.join(_CAMPOS_TRECHO)}, 1 - (embedding <=> :vetor) AS similaridade "
    "FROM copilot.trechos_corpus ORDER BY embedding <=> :vetor LIMIT :k"
).bindparams(bindparam("vetor", type_=Vector(DIMENSAO)))


class PostgresTrechosRepositorio(TrechosRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def hashes_por_documento(self) -> dict[str, str]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT DISTINCT documento, hash_documento FROM copilot.trechos_corpus")
            ).all()
        return {row.documento: row.hash_documento for row in rows}

    def substituir_documento(
        self, documento: str, hash_documento: str, trechos: list[TrechoIndexado]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(_DELETE, {"documento": documento})
            if trechos:
                conn.execute(
                    _INSERT,
                    [
                        {**trecho.model_dump(), "hash_documento": hash_documento}
                        for trecho in trechos
                    ],
                )

    def remover_documento(self, documento: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(_DELETE, {"documento": documento})

    def buscar_similares(self, vetor: list[float], k: int) -> list[TrechoRecuperado]:
        with self._engine.connect() as conn:
            rows = conn.execute(_BUSCAR, {"vetor": vetor, "k": k}).all()
        return [TrechoRecuperado.model_validate(row._asdict()) for row in rows]
