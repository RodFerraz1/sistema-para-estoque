"""Implementação Postgres do repositório do módulo `reposicao` sobre
`copilot.verificacoes_gondola`."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.reposicao.repositorio import VerificacoesRepositorio
from src.reposicao.schemas import VerificacaoGondola

_CAMPOS = list(VerificacaoGondola.model_fields)
_INSERT = text(
    f"INSERT INTO copilot.verificacoes_gondola ({', '.join(_CAMPOS)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS)})"
)
_SELECT = f"SELECT {', '.join(_CAMPOS)} FROM copilot.verificacoes_gondola"


class PostgresVerificacoesRepositorio(VerificacoesRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, verificacao: VerificacaoGondola) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT, verificacao.model_dump())

    def listar(self, sku_code: str) -> list[VerificacaoGondola]:
        # O id em texto desempata como o `str(id)` da versão em memória.
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT} WHERE sku_code = :sku_code ORDER BY criado_em DESC, id::text DESC"),
                {"sku_code": sku_code},
            ).all()
        return [VerificacaoGondola.model_validate(row._asdict()) for row in rows]

    def ultimas(self) -> dict[str, VerificacaoGondola]:
        sql = (
            f"SELECT DISTINCT ON (sku_code) {', '.join(_CAMPOS)} FROM copilot.verificacoes_gondola "
            "ORDER BY sku_code, criado_em DESC, id::text DESC"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).all()
        return {row.sku_code: VerificacaoGondola.model_validate(row._asdict()) for row in rows}
