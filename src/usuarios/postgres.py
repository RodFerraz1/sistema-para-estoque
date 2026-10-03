"""Implementações Postgres dos repositórios do módulo `usuarios` sobre `copilot.usuarios`,
`copilot.sessoes` e `copilot.tentativas_login`."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from src.usuarios.repositorio import (
    EmailJaCadastrado,
    SessoesRepositorio,
    TentativasLoginRepositorio,
    UsuariosRepositorio,
)
from src.usuarios.schemas import Sessao, Usuario

_CAMPOS_USUARIO = list(Usuario.model_fields)
_INSERT_USUARIO = text(
    f"INSERT INTO copilot.usuarios ({', '.join(_CAMPOS_USUARIO)}) "
    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_USUARIO)})"
)
_SELECT_USUARIO = f"SELECT {', '.join(_CAMPOS_USUARIO)} FROM copilot.usuarios"
_EMAIL_UNICO = "usuarios_email_key"


class PostgresUsuariosRepositorio(UsuariosRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, usuario: Usuario) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(_INSERT_USUARIO, usuario.model_dump())
        except IntegrityError as e:
            if _EMAIL_UNICO in str(e.orig):
                raise EmailJaCadastrado(usuario.email) from e
            raise

    def _um(self, filtro: str, parametros: dict[str, object]) -> Usuario | None:
        with self._engine.connect() as conn:
            row = conn.execute(text(f"{_SELECT_USUARIO} WHERE {filtro}"), parametros).one_or_none()
        return None if row is None else Usuario.model_validate(row._asdict())

    def por_id(self, usuario_id: UUID) -> Usuario | None:
        return self._um("id = :id", {"id": usuario_id})

    def por_email(self, email: str) -> Usuario | None:
        return self._um("email = :email", {"email": email})

    def registrar_acesso(self, usuario_id: UUID, quando: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE copilot.usuarios SET ultimo_acesso_em = :quando WHERE id = :id"),
                {"id": usuario_id, "quando": quando},
            )


_CAMPOS_SESSAO = list(Sessao.model_fields)


class PostgresSessoesRepositorio(SessoesRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def gravar(self, sessao: Sessao) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO copilot.sessoes ({', '.join(_CAMPOS_SESSAO)}) "
                    f"VALUES ({', '.join(f':{c}' for c in _CAMPOS_SESSAO)})"
                ),
                sessao.model_dump(),
            )

    def por_token_hash(self, token_hash: str) -> Sessao | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {', '.join(_CAMPOS_SESSAO)} FROM copilot.sessoes WHERE token_hash = :token_hash"),
                {"token_hash": token_hash},
            ).one_or_none()
        return None if row is None else Sessao.model_validate(row._asdict())

    def renovar(self, token_hash: str, expira_em: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE copilot.sessoes SET expira_em = :expira_em WHERE token_hash = :token_hash"),
                {"token_hash": token_hash, "expira_em": expira_em},
            )

    def revogar(self, token_hash: str, quando: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE copilot.sessoes SET revogada_em = :quando "
                    "WHERE token_hash = :token_hash AND revogada_em IS NULL"
                ),
                {"token_hash": token_hash, "quando": quando},
            )


class PostgresTentativasLoginRepositorio(TentativasLoginRepositorio):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def registrar_falha(self, email: str, quando: datetime) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("INSERT INTO copilot.tentativas_login (email, tentada_em) VALUES (:email, :quando)"),
                {"email": email, "quando": quando},
            )

    def falhas_desde(self, email: str, desde: datetime) -> list[datetime]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT tentada_em FROM copilot.tentativas_login "
                    "WHERE email = :email AND tentada_em >= :desde ORDER BY tentada_em"
                ),
                {"email": email, "desde": desde},
            ).all()
        return [row.tentada_em for row in rows]

    def limpar(self, email: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM copilot.tentativas_login WHERE email = :email"), {"email": email})
