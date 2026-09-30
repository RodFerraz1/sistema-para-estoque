"""Adapters Postgres do módulo `ai`: `TrechosRepositorio` sobre
`copilot.trechos_corpus` e `RegistrosDecisao` sobre `copilot.registros_decisao`.

A similaridade é 1 - distância de cosseno (operador `<=>` do pgvector). Sem
índice vetorial: com poucas centenas de linhas a busca exata é suficiente.
"""
from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine

from src.ai.embeddings import DIMENSAO
from src.ai.registro import RegistrosDecisao
from src.ai.repositorio import TrechosRepositorio
from src.ai.schemas import RegistroDecisao, TrechoIndexado, TrechoRecuperado

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


_CAMPOS_REGISTRO = list(RegistroDecisao.model_fields)

_INSERT_REGISTRO = text(
    f"INSERT INTO copilot.registros_decisao ({', '.join(_CAMPOS_REGISTRO)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_REGISTRO)})"
).bindparams(bindparam("entendimento", type_=JSONB))

_LISTAR_REGISTROS = text(
    f"SELECT {', '.join(_CAMPOS_REGISTRO)} FROM copilot.registros_decisao "
    "ORDER BY criado_em DESC LIMIT :limite"
)


class PostgresRegistrosDecisao(RegistrosDecisao):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, registro: RegistroDecisao) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                _INSERT_REGISTRO,
                {**registro.model_dump(), "entendimento": registro.entendimento.model_dump(mode="json")},
            )

    def listar(self, limite: int) -> list[RegistroDecisao]:
        with self._engine.connect() as conn:
            rows = conn.execute(_LISTAR_REGISTROS, {"limite": limite}).all()
        return [RegistroDecisao.model_validate(row._asdict()) for row in rows]
