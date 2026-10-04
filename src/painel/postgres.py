"""Implementações Postgres dos repositórios do módulo `painel` sobre `copilot.avisos`,
`copilot.decisoes_compra` e `copilot.cobrancas_entrega`."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.painel.repositorio import AvisosRepositorio, CobrancasRepositorio, DecisoesRepositorio
from src.painel.schemas import Aviso, CobrancaEntrega, DecisaoCompra

_CAMPOS_AVISO = list(Aviso.model_fields)
_INSERT_AVISO = text(
    f"INSERT INTO copilot.avisos ({', '.join(_CAMPOS_AVISO)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_AVISO)})"
)
_SELECT_AVISO = f"SELECT {', '.join(_CAMPOS_AVISO)} FROM copilot.avisos"
# O id em texto desempata como o `str(id)` da versão em memória.
_ORDEM = "ORDER BY criado_em DESC, id::text DESC"


class PostgresAvisosRepositorio(AvisosRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, aviso: Aviso) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT_AVISO, aviso.model_dump())

    def listar(self, sku_code: str | None = None) -> list[Aviso]:
        filtro = "" if sku_code is None else "WHERE sku_code = :sku_code"
        with self._engine.connect() as conn:
            rows = conn.execute(text(f"{_SELECT_AVISO} {filtro} {_ORDEM}"), {"sku_code": sku_code}).all()
        return [Aviso.model_validate(row._asdict()) for row in rows]


_CAMPOS_DECISAO = list(DecisaoCompra.model_fields)
_INSERT_DECISAO = text(
    f"INSERT INTO copilot.decisoes_compra ({', '.join(_CAMPOS_DECISAO)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_DECISAO)})"
)
_SELECT_DECISAO = f"SELECT {', '.join(_CAMPOS_DECISAO)} FROM copilot.decisoes_compra"


class PostgresDecisoesRepositorio(DecisoesRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, decisao: DecisaoCompra) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT_DECISAO, decisao.model_dump())

    def listar(self, sku_code: str) -> list[DecisaoCompra]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT_DECISAO} WHERE sku_code = :sku_code {_ORDEM}"), {"sku_code": sku_code}
            ).all()
        return [DecisaoCompra.model_validate(row._asdict()) for row in rows]

    def ultimas(self) -> dict[str, DecisaoCompra]:
        sql = (
            f"SELECT DISTINCT ON (sku_code) {', '.join(_CAMPOS_DECISAO)} FROM copilot.decisoes_compra "
            "ORDER BY sku_code, criado_em DESC, id::text DESC"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).all()
        return {row.sku_code: DecisaoCompra.model_validate(row._asdict()) for row in rows}


_CAMPOS_COBRANCA = list(CobrancaEntrega.model_fields)
_INSERT_COBRANCA = text(
    f"INSERT INTO copilot.cobrancas_entrega ({', '.join(_CAMPOS_COBRANCA)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_COBRANCA)})"
)
_SELECT_COBRANCA = f"SELECT {', '.join(_CAMPOS_COBRANCA)} FROM copilot.cobrancas_entrega"


class PostgresCobrancasRepositorio(CobrancasRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, cobranca: CobrancaEntrega) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT_COBRANCA, cobranca.model_dump())

    def listar(self, pedido_id: UUID) -> list[CobrancaEntrega]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT_COBRANCA} WHERE pedido_id = :pedido_id {_ORDEM}"), {"pedido_id": pedido_id}
            ).all()
        return [CobrancaEntrega.model_validate(row._asdict()) for row in rows]

    def ultimas(self) -> dict[UUID, CobrancaEntrega]:
        sql = (
            f"SELECT DISTINCT ON (pedido_id) {', '.join(_CAMPOS_COBRANCA)} FROM copilot.cobrancas_entrega "
            "ORDER BY pedido_id, criado_em DESC, id::text DESC"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).all()
        return {row.pedido_id: CobrancaEntrega.model_validate(row._asdict()) for row in rows}
