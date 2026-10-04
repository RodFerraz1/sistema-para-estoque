"""O autor dos avisos, decisões e registros de decisão dos testes de contrato. `usuario_id` aponta para
`copilot.usuarios`, então no Postgres o autor precisa existir enquanto o teste roda."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from src.db.engine import get_engine
from src.usuarios.postgres import PostgresUsuariosRepositorio
from src.usuarios.schemas import Usuario

AUTOR = Usuario(
    id=UUID("00000000-0000-0000-0000-00000000a070"),
    nome="Autor do Contrato",
    email="autor@contrato-autoria.teste",
    senha_hash="$argon2id$falso",
    papeis=["vendas", "comprador"],
    ativo=False,
    criado_em=datetime(2026, 10, 1, tzinfo=UTC),
    ultimo_acesso_em=None,
)


@contextmanager
def autor_no_banco() -> Iterator[None]:
    """Grava o `AUTOR` e o apaga no fim. Quem usa apaga antes as linhas que apontam para ele."""
    PostgresUsuariosRepositorio(get_engine()).gravar(AUTOR)
    try:
        yield
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM copilot.usuarios WHERE id = :id"), {"id": AUTOR.id})
