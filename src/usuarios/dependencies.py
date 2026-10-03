"""Dependências do FastAPI do módulo `usuarios`: a sessão do cookie e os papéis.

Nos testes HTTP, o `conftest.py` da raiz troca `usuario_atual` por um usuário fake e
desliga `exige_x_requested_with`. Ver o docstring de `usuario_logado` lá.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, Response, status

from src.db.config import get_settings
from src.db.engine import get_engine
from src.usuarios.postgres import (
    PostgresSessoesRepositorio,
    PostgresTentativasLoginRepositorio,
    PostgresUsuariosRepositorio,
)
from src.usuarios.repositorio import SessoesRepositorio, TentativasLoginRepositorio, UsuariosRepositorio
from src.usuarios.schemas import Papel, Usuario
from src.usuarios.service import DURACAO_DA_SESSAO, Relogio, Usuarios, agora_utc

NOME_DO_COOKIE = "copilot_sessao"
METODOS_QUE_MUDAM_ESTADO = {"POST", "PUT", "PATCH", "DELETE"}


def get_usuarios_repositorio() -> UsuariosRepositorio:
    return PostgresUsuariosRepositorio(get_engine())


def get_sessoes_repositorio() -> SessoesRepositorio:
    return PostgresSessoesRepositorio(get_engine())


def get_tentativas_login_repositorio() -> TentativasLoginRepositorio:
    return PostgresTentativasLoginRepositorio(get_engine())


def get_relogio() -> Relogio:
    return agora_utc


def get_usuarios(
    usuarios: UsuariosRepositorio = Depends(get_usuarios_repositorio),
    sessoes: SessoesRepositorio = Depends(get_sessoes_repositorio),
    tentativas: TentativasLoginRepositorio = Depends(get_tentativas_login_repositorio),
    relogio: Relogio = Depends(get_relogio),
) -> Usuarios:
    return Usuarios(usuarios, sessoes, tentativas, relogio=relogio)


def gravar_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        NOME_DO_COOKIE,
        token,
        max_age=int(DURACAO_DA_SESSAO.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=get_settings().ambiente != "local",
    )


def apagar_cookie(response: Response) -> None:
    response.delete_cookie(NOME_DO_COOKIE, httponly=True, samesite="lax", secure=get_settings().ambiente != "local")


def exige_x_requested_with(request: Request) -> None:
    """Defesa contra CSRF junto com o `SameSite`: outro site não manda esse cabeçalho sem
    passar pelo CORS. Aplicada no app inteiro."""
    if request.method in METODOS_QUE_MUDAM_ESTADO and "x-requested-with" not in request.headers:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Falta o cabeçalho X-Requested-With.")


def usuario_atual(request: Request, response: Response, usuarios: Usuarios = Depends(get_usuarios)) -> Usuario:
    """401 sem sessão aberta. Renova o cookie a cada uso."""
    token = request.cookies.get(NOME_DO_COOKIE)
    usuario = usuarios.usuario_da_sessao(token) if token else None
    if token is None or usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entre com o seu e-mail e senha.")
    gravar_cookie(response, token)
    return usuario


def exige_papel(*papeis: Papel) -> Callable[[Usuario], Usuario]:
    """403 para quem não tem nenhum dos `papeis`."""

    def dependencia(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if not set(papeis) & set(usuario.papeis):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Esta parte do Copilot não é do seu papel."
            )
        return usuario

    return dependencia
