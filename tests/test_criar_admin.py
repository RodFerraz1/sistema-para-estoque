"""O comando que cria o primeiro admin, contra o Postgres (pulado sem banco)."""
from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from sqlalchemy import text

from scripts.criar_admin import main
from src.db.engine import get_engine
from src.usuarios.postgres import PostgresUsuariosRepositorio

EMAIL = "admin@criar-admin.teste"


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.usuarios LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_disponivel(), reason="Postgres com copilot.usuarios precisa estar disponível")


@pytest.fixture(autouse=True)
def _apagar() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM copilot.usuarios WHERE email = :email"), {"email": EMAIL})


def test_cria_o_admin_com_a_senha_da_entrada(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("uma-senha-boa\n"))

    assert main(["--nome", "Rodrigo", "--email", "Admin@Criar-Admin.teste"]) == 0

    usuario = PostgresUsuariosRepositorio(get_engine()).por_email(EMAIL)
    assert usuario is not None and usuario.papeis == ["admin"] and usuario.nome == "Rodrigo"
    assert "uma-senha-boa" not in usuario.senha_hash
    assert "criado" in capsys.readouterr().out


def test_senha_curta_e_email_repetido_falham(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("curta\n"))
    assert main(["--nome", "Rodrigo", "--email", EMAIL]) == 1
    assert "8 caracteres" in capsys.readouterr().err

    monkeypatch.setattr("sys.stdin", io.StringIO("uma-senha-boa\n"))
    assert main(["--nome", "Rodrigo", "--email", EMAIL, "--papeis", "comprador,admin"]) == 0
    monkeypatch.setattr("sys.stdin", io.StringIO("uma-senha-boa\n"))
    assert main(["--nome", "Outro", "--email", EMAIL]) == 1
    assert "Já existe" in capsys.readouterr().err
