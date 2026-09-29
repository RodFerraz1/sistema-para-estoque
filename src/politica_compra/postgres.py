"""Implementação Postgres do `PoliticaCompraRepositorio` sobre
`copilot.politicas_compra`. Só faz `SELECT` e `INSERT`: a tabela é
append-only.

Cada campo de `ParametrosPolitica` é uma coluna de mesmo nome.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import ParametrosPolitica, PoliticaCompra


_CAMPOS = list(ParametrosPolitica.model_fields)
_SELECT = (
    f"SELECT versao, criada_em, {', '.join(_CAMPOS)} FROM copilot.politicas_compra"
)
_INSERT = (
    f"INSERT INTO copilot.politicas_compra ({', '.join(_CAMPOS)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS)}) "
    f"RETURNING versao, criada_em, {', '.join(_CAMPOS)}"
)


def _row_to_politica(row: Row) -> PoliticaCompra:
    return PoliticaCompra(
        versao=row.versao,
        criada_em=row.criada_em,
        parametros=ParametrosPolitica.model_validate(
            {c: getattr(row, c) for c in _CAMPOS}
        ),
    )


class PostgresPoliticaCompraRepositorio(PoliticaCompraRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ativa(self) -> PoliticaCompra:
        with self._engine.connect() as conn:
            row = conn.execute(text(_SELECT + " ORDER BY versao DESC LIMIT 1")).one()
        return _row_to_politica(row)

    def versao(self, versao: int) -> PoliticaCompra | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SELECT + " WHERE versao = :versao"), {"versao": versao}
            ).one_or_none()
        return _row_to_politica(row) if row is not None else None

    def salvar_nova_versao(self, parametros: ParametrosPolitica) -> PoliticaCompra:
        with self._engine.begin() as conn:
            row = conn.execute(text(_INSERT), parametros.model_dump(mode="json")).one()
        return _row_to_politica(row)
