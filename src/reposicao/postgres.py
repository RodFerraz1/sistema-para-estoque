"""Implementação Postgres dos repositórios do módulo `reposicao` sobre
`copilot.verificacoes_gondola`, `copilot.setores`, `copilot.setores_sku`,
`copilot.avisos_gondola` e `copilot.capacidades_gondola`."""
from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from src.reposicao.repositorio import (
    AvisosGondolaRepositorio,
    CapacidadesGondolaRepositorio,
    SetoresRepositorio,
    SetorJaExiste,
    VerificacoesRepositorio,
)
from src.reposicao.schemas import AvisoGondola, CapacidadeGondola, Setor, SetorDoSku, VerificacaoGondola

# O id em texto desempata como o `str(id)` das versões em memória.
_ORDEM = "ORDER BY criado_em DESC, id::text DESC"

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
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT} WHERE sku_code = :sku_code {_ORDEM}"), {"sku_code": sku_code}
            ).all()
        return [VerificacaoGondola.model_validate(row._asdict()) for row in rows]

    def dos_skus(self, sku_codes: Collection[str], desde: datetime) -> list[VerificacaoGondola]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT} WHERE sku_code = ANY(:sku_codes) AND criado_em >= :desde {_ORDEM}"),
                {"sku_codes": list(sku_codes), "desde": desde},
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


_NOME_UNICO = "setores_nome_key"
_CAMPOS_SETOR_DO_SKU = list(SetorDoSku.model_fields)
_SELECT_SETOR_DO_SKU = f"SELECT {', '.join(_CAMPOS_SETOR_DO_SKU)} FROM copilot.setores_sku"


class PostgresSetoresRepositorio(SetoresRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def listar(self) -> list[Setor]:
        with self._engine.connect() as conn:
            rows = conn.execute(text("SELECT id, nome, ativo FROM copilot.setores ORDER BY lower(nome)")).all()
        return [Setor.model_validate(row._asdict()) for row in rows]

    def carregar(self, setor_id: UUID) -> Setor | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT id, nome, ativo FROM copilot.setores WHERE id = :id"), {"id": setor_id}
            ).one_or_none()
        return None if row is None else Setor.model_validate(row._asdict())

    def gravar(self, setor: Setor) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO copilot.setores (id, nome, ativo) VALUES (:id, :nome, :ativo) "
                        "ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome, ativo = EXCLUDED.ativo"
                    ),
                    setor.model_dump(),
                )
        except IntegrityError as e:
            if _NOME_UNICO in str(e.orig):
                raise SetorJaExiste(setor.nome) from e
            raise

    def lembrar(self, setor_do_sku: SetorDoSku) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO copilot.setores_sku ({', '.join(_CAMPOS_SETOR_DO_SKU)}) "
                    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_SETOR_DO_SKU)}) "
                    "ON CONFLICT (sku_code) DO UPDATE SET setor_id = EXCLUDED.setor_id, "
                    "atualizado_em = EXCLUDED.atualizado_em, usuario_id = EXCLUDED.usuario_id"
                ),
                setor_do_sku.model_dump(),
            )

    def do_sku(self, sku_code: str) -> SetorDoSku | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(f"{_SELECT_SETOR_DO_SKU} WHERE sku_code = :sku_code"), {"sku_code": sku_code}
            ).one_or_none()
        return None if row is None else SetorDoSku.model_validate(row._asdict())

    def dos_skus(self) -> dict[str, SetorDoSku]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(_SELECT_SETOR_DO_SKU)).all()
        return {row.sku_code: SetorDoSku.model_validate(row._asdict()) for row in rows}


_CAMPOS_AVISO = list(AvisoGondola.model_fields)
_INSERT_AVISO = text(
    f"INSERT INTO copilot.avisos_gondola ({', '.join(_CAMPOS_AVISO)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_AVISO)})"
)
_SELECT_AVISO = f"SELECT {', '.join(_CAMPOS_AVISO)} FROM copilot.avisos_gondola"


class PostgresAvisosGondolaRepositorio(AvisosGondolaRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, aviso: AvisoGondola) -> None:
        with self._engine.begin() as conn:
            conn.execute(_INSERT_AVISO, aviso.model_dump())

    def listar(self, sku_code: str | None = None) -> list[AvisoGondola]:
        filtro = "" if sku_code is None else "WHERE sku_code = :sku_code"
        with self._engine.connect() as conn:
            rows = conn.execute(text(f"{_SELECT_AVISO} {filtro} {_ORDEM}"), {"sku_code": sku_code}).all()
        return [AvisoGondola.model_validate(row._asdict()) for row in rows]

    def do_usuario(self, usuario_id: UUID, desde: datetime) -> list[AvisoGondola]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"{_SELECT_AVISO} WHERE usuario_id = :usuario_id AND criado_em >= :desde {_ORDEM}"),
                {"usuario_id": usuario_id, "desde": desde},
            ).all()
        return [AvisoGondola.model_validate(row._asdict()) for row in rows]


_CAMPOS_CAPACIDADE = list(CapacidadeGondola.model_fields)
_SELECT_CAPACIDADE = f"SELECT {', '.join(_CAMPOS_CAPACIDADE)} FROM copilot.capacidades_gondola"


class PostgresCapacidadesGondolaRepositorio(CapacidadesGondolaRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, capacidade: CapacidadeGondola) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO copilot.capacidades_gondola ({', '.join(_CAMPOS_CAPACIDADE)}) "
                    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_CAPACIDADE)}) "
                    "ON CONFLICT (produto_id) DO UPDATE SET capacidade = EXCLUDED.capacidade, "
                    "usuario_id = EXCLUDED.usuario_id, atualizado_em = EXCLUDED.atualizado_em"
                ),
                capacidade.model_dump(),
            )

    def do_produto(self, produto_id: UUID) -> CapacidadeGondola | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(f"{_SELECT_CAPACIDADE} WHERE produto_id = :produto_id"), {"produto_id": produto_id}
            ).one_or_none()
        return None if row is None else CapacidadeGondola.model_validate(row._asdict())

    def todas(self) -> dict[UUID, CapacidadeGondola]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(_SELECT_CAPACIDADE)).all()
        return {row.produto_id: CapacidadeGondola.model_validate(row._asdict()) for row in rows}
