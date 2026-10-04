"""Implementação Postgres do repositório do módulo `notificacoes` sobre
`copilot.episodios_alerta`."""
from __future__ import annotations

import json
from collections.abc import Collection
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.notificacoes.repositorio import EpisodiosRepositorio, a_abrir_e_a_fechar
from src.notificacoes.schemas import Condicao, Episodio, TipoEpisodio
from src.usuarios.schemas import Papel

_CAMPOS = list(Episodio.model_fields)
_SELECT = f"SELECT {', '.join(_CAMPOS)} FROM copilot.episodios_alerta"
_INSERT = text(
    f"INSERT INTO copilot.episodios_alerta ({', '.join(_CAMPOS)}) "
    f"VALUES ({', '.join('CAST(:detalhe AS jsonb)' if c == 'detalhe' else f':{c}' for c in _CAMPOS)})"
)
# A varredura inteira roda com esta trava, para duas ao mesmo tempo não abrirem a mesma
# condição duas vezes. O índice único parcial é a última defesa.
_TRAVA = text("SELECT pg_advisory_xact_lock(hashtext('copilot.episodios_alerta'))")


def _linha(episodio: Episodio) -> dict[str, Any]:
    return {**episodio.model_dump(), "detalhe": json.dumps(episodio.detalhe)}


class PostgresEpisodiosRepositorio(EpisodiosRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def varrer(self, tipos: Collection[TipoEpisodio], condicoes: list[Condicao], agora: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(_TRAVA)
            rows = conn.execute(
                text(f"{_SELECT} WHERE fechado_em IS NULL AND tipo = ANY(:tipos)"), {"tipos": list(tipos)}
            ).all()
            abertos = [Episodio.model_validate(row._asdict()) for row in rows]
            novas, a_fechar = a_abrir_e_a_fechar(abertos, [c for c in condicoes if c.tipo in tipos])
            if a_fechar:
                conn.execute(
                    text("UPDATE copilot.episodios_alerta SET fechado_em = :agora WHERE id = ANY(:ids)"),
                    {"agora": agora, "ids": [e.id for e in a_fechar]},
                )
            if novas:
                conn.execute(
                    _INSERT,
                    [
                        _linha(Episodio(id=uuid4(), aberto_em=agora, fechado_em=None, **c.model_dump()))
                        for c in novas
                    ],
                )

    def gravar(self, episodio: Episodio) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT, _linha(episodio))

    def dos_papeis(self, papeis: Collection[Papel], limite: int) -> list[Episodio]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"{_SELECT} WHERE papel_destino = ANY(:papeis) "
                    "ORDER BY aberto_em DESC, id::text DESC LIMIT :limite"
                ),
                {"papeis": list(papeis), "limite": limite},
            ).all()
        return [Episodio.model_validate(row._asdict()) for row in rows]

    def abertos_depois(self, papeis: Collection[Papel], desde: datetime | None) -> int:
        with self._engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT count(*) FROM copilot.episodios_alerta WHERE papel_destino = ANY(:papeis) "
                    "AND (CAST(:desde AS timestamptz) IS NULL OR aberto_em > :desde)"
                ),
                {"papeis": list(papeis), "desde": desde},
            ).scalar_one()
