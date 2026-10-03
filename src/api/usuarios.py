"""Endpoints HTTP do login, da saída e do usuário logado (ADR-0007)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.api.schemas import LoginRequest, UsuarioResponse
from src.usuarios.dependencies import NOME_DO_COOKIE, apagar_cookie, get_usuarios, gravar_cookie, usuario_atual
from src.usuarios.schemas import Usuario
from src.usuarios.service import CredenciaisInvalidas, LoginBloqueado, Usuarios

router = APIRouter(tags=["usuarios"])


def usuario_to_response(usuario: Usuario) -> UsuarioResponse:
    return UsuarioResponse(id=usuario.id, nome=usuario.nome, email=usuario.email, papeis=usuario.papeis)


@router.post("/login", response_model=UsuarioResponse)
def login(corpo: LoginRequest, response: Response, usuarios: Usuarios = Depends(get_usuarios)) -> UsuarioResponse:
    """Abre a sessão no cookie. 401 com e-mail ou senha errados, 429 com o e-mail bloqueado."""
    try:
        usuario, token = usuarios.entrar(corpo.email, corpo.senha)
    except CredenciaisInvalidas as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    except LoginBloqueado as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e
    gravar_cookie(response, token)
    return usuario_to_response(usuario)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(usuario_atual)])
def logout(request: Request, usuarios: Usuarios = Depends(get_usuarios)) -> Response:
    """Revoga a sessão e apaga o cookie."""
    token = request.cookies.get(NOME_DO_COOKIE)
    if token:
        usuarios.sair(token)
    # Uma resposta própria descarta o cookie renovado por `usuario_atual`.
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    apagar_cookie(response)
    return response


@router.get("/eu", response_model=UsuarioResponse)
def eu(usuario: Usuario = Depends(usuario_atual)) -> UsuarioResponse:
    return usuario_to_response(usuario)
