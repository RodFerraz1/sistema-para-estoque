"""Implementação Postgres da fila de aprovação sobre `copilot.sugestoes_fila`.

`dados` guarda a sugestão com os sinais e o SKU; `sku_code`, `destaque` e
`cobertura_na_chegada_sem_compra_meses` ficam em colunas para ordenar a fila.
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine, Row

from src.aprovacao.repositorio import CAMPOS_DA_DECISAO, SugestoesFila
from src.aprovacao.schemas import StatusSugestao, SugestaoNaFila

_COLUNAS = (
    "id",
    "criado_em",
    "sku_code",
    "status",
    "destaque",
    "cobertura_na_chegada_sem_compra_meses",
    "dados",
    "faixa",
    "decidido_em",
    "decidido_por",
    "quantidade_aprovada",
    "justificativa",
    "motivo_rejeicao",
    "pedido_compra_id",
)
_SELECT = f"SELECT {', '.join(_COLUNAS)} FROM copilot.sugestoes_fila"
_ORDEM_DA_FILA = (
    "ORDER BY destaque DESC, cobertura_na_chegada_sem_compra_meses, sku_code COLLATE \"C\", id"
)
_ORDEM_DAS_DECIDIDAS = "ORDER BY decidido_em DESC NULLS LAST, criado_em DESC, id"

_INSERT = text(
    f"INSERT INTO copilot.sugestoes_fila ({', '.join(_COLUNAS)}) "
    f"VALUES ({', '.join(f':{c}' for c in _COLUNAS)})"
).bindparams(bindparam("dados", type_=JSONB), bindparam("faixa", type_=JSONB))

_SUBSTITUIR = text("UPDATE copilot.sugestoes_fila SET status = 'substituida' WHERE status = 'pendente'")

_DECIDIR = text(
    "UPDATE copilot.sugestoes_fila SET "
    + ", ".join(f"{c} = :{c}" for c in CAMPOS_DA_DECISAO)
    + " WHERE id = :id AND status = 'pendente'"
).bindparams(bindparam("faixa", type_=JSONB))


def _linha(s: SugestaoNaFila) -> dict[str, object]:
    return {
        **s.model_dump(include=set(_COLUNAS)),
        "sku_code": s.sku_code,
        "cobertura_na_chegada_sem_compra_meses": s.cobertura_na_chegada_sem_compra_meses,
        "dados": s.model_dump(mode="json", include={"sku", "sugestao"}),
        "faixa": s.faixa.model_dump(mode="json"),
    }


def _sugestao(row: Row) -> SugestaoNaFila:
    campos = row._asdict()
    return SugestaoNaFila.model_validate({**campos, **campos.pop("dados")})


class PostgresSugestoesFila(SugestoesFila):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def substituir_pendentes(self, novas: Sequence[SugestaoNaFila]) -> int:
        with self._engine.begin() as conn:
            substituidas = conn.execute(_SUBSTITUIR).rowcount
            if novas:
                conn.execute(_INSERT, [_linha(s) for s in novas])
        return substituidas

    def listar(self, status: StatusSugestao) -> list[SugestaoNaFila]:
        ordem = _ORDEM_DA_FILA if status == "pendente" else _ORDEM_DAS_DECIDIDAS
        with self._engine.connect() as conn:
            rows = conn.execute(text(f"{_SELECT} WHERE status = :status {ordem}"), {"status": status}).all()
        return [_sugestao(row) for row in rows]

    def carregar(self, id: UUID) -> SugestaoNaFila | None:
        with self._engine.connect() as conn:
            row = conn.execute(text(f"{_SELECT} WHERE id = :id"), {"id": id}).one_or_none()
        return _sugestao(row) if row is not None else None

    def registrar_decisao(self, decidida: SugestaoNaFila) -> bool:
        with self._engine.begin() as conn:
            linhas = conn.execute(_DECIDIR, _linha(decidida)).rowcount
        return linhas == 1
