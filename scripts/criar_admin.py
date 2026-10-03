"""Cria o primeiro admin do Copilot (ADR-0007), pedindo a senha no terminal, para não
existir senha padrão no código. As outras pessoas o admin cadastra pela tela.

`--papeis` troca os papéis (padrão: só `admin`), para criar pessoas de teste no ambiente
local. Sem terminal (senha vinda de um pipe), lê a senha da primeira linha da entrada.

    uv run python -m scripts.criar_admin --nome "Rodrigo" --email rodrigo@loja.com
    uv run python -m scripts.criar_admin --nome "Carla" --email carla@loja.com --papeis comprador
"""
from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence
from typing import TextIO, cast

from src.db.engine import get_engine
from src.usuarios.postgres import (
    PostgresSessoesRepositorio,
    PostgresTentativasLoginRepositorio,
    PostgresUsuariosRepositorio,
)
from src.usuarios.repositorio import EmailJaCadastrado
from src.usuarios.schemas import PAPEIS, Papel
from src.usuarios.service import DadosInvalidos, Usuarios


def _papeis(texto: str) -> list[Papel]:
    papeis = [p.strip() for p in texto.split(",") if p.strip()]
    desconhecidos = [p for p in papeis if p not in PAPEIS]
    if desconhecidos:
        raise argparse.ArgumentTypeError(f"papel desconhecido: {', '.join(desconhecidos)} (use {', '.join(PAPEIS)})")
    return cast(list[Papel], papeis)


def ler_senha(entrada: TextIO) -> str:
    if not entrada.isatty():
        return entrada.readline().rstrip("\n")
    senha = getpass.getpass("Senha: ")
    if getpass.getpass("Repita a senha: ") != senha:
        raise DadosInvalidos("As senhas não conferem.")
    return senha


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nome", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--papeis", type=_papeis, default=["admin"], help="separados por vírgula")
    args = parser.parse_args(argv)
    engine = get_engine()
    usuarios = Usuarios(
        PostgresUsuariosRepositorio(engine),
        PostgresSessoesRepositorio(engine),
        PostgresTentativasLoginRepositorio(engine),
    )
    try:
        usuario = usuarios.criar(args.nome, args.email, ler_senha(sys.stdin), args.papeis)
    except (DadosInvalidos, EmailJaCadastrado) as e:
        print(e, file=sys.stderr)
        return 1
    print(f"{usuario.nome} ({usuario.email}) criado com os papéis: {', '.join(usuario.papeis)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
