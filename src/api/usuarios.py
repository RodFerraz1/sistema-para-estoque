"""Endpoints HTTP do login, da saída, do usuário logado e da gestão de usuários pelo
admin (ADR-0007)."""
from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.api.schemas import (
    CriarUsuarioRequest,
    LoginRequest,
    PapeisRequest,
    RedefinirSenhaRequest,
    TrocarSenhaRequest,
    UsuarioAdminResponse,
    UsuarioResponse,
)
from src.usuarios.dependencies import (
    NOME_DO_COOKIE,
    apagar_cookie,
    exige_papel,
    get_usuarios,
    gravar_cookie,
    usuario_atual,
)
from src.usuarios.repositorio import EmailJaCadastrado
from src.usuarios.schemas import Usuario
from src.usuarios.service import (
    CredenciaisInvalidas,
    DadosInvalidos,
    LoginBloqueado,
    SenhaAtualErrada,
    UsuarioNaoEncontrado,
    Usuarios,
)

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


@router.put("/eu/senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(
    corpo: TrocarSenhaRequest, usuario: Usuario = Depends(usuario_atual), usuarios: Usuarios = Depends(get_usuarios)
) -> None:
    """422 com a senha atual errada ou a nova curta. A sessão continua aberta."""
    try:
        usuarios.trocar_senha(usuario, corpo.senha_atual, corpo.nova_senha)
    except (SenhaAtualErrada, DadosInvalidos) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e


def admin_to_response(usuario: Usuario) -> UsuarioAdminResponse:
    return UsuarioAdminResponse.model_validate(usuario.model_dump(exclude={"senha_hash"}))


@router.get("/usuarios", response_model=list[UsuarioAdminResponse], dependencies=[Depends(exige_papel("admin"))])
def listar_usuarios(usuarios: Usuarios = Depends(get_usuarios)) -> list[UsuarioAdminResponse]:
    """Todos, ativos ou não, pelo nome."""
    return [admin_to_response(u) for u in usuarios.listar()]


@router.post(
    "/usuarios",
    response_model=UsuarioAdminResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(exige_papel("admin"))],
)
def criar_usuario(corpo: CriarUsuarioRequest, usuarios: Usuarios = Depends(get_usuarios)) -> UsuarioAdminResponse:
    """409 com e-mail já cadastrado, 422 sem nome, sem papel, com e-mail inválido ou senha curta."""
    try:
        return admin_to_response(usuarios.criar(corpo.nome, corpo.email, corpo.senha, corpo.papeis))
    except EmailJaCadastrado as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except DadosInvalidos as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e


def _mudar(acao: Callable[[], Usuario]) -> UsuarioAdminResponse:
    try:
        return admin_to_response(acao())
    except UsuarioNaoEncontrado as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DadosInvalidos as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e


@router.put("/usuarios/{usuario_id}/papeis", response_model=UsuarioAdminResponse)
def mudar_papeis(
    usuario_id: UUID,
    corpo: PapeisRequest,
    admin: Usuario = Depends(exige_papel("admin")),
    usuarios: Usuarios = Depends(get_usuarios),
) -> UsuarioAdminResponse:
    """404 sem a pessoa, 422 sem papel ou quando o admin tira o próprio papel de admin."""
    return _mudar(lambda: usuarios.mudar_papeis(admin, usuario_id, corpo.papeis))


@router.post("/usuarios/{usuario_id}/desativar", response_model=UsuarioAdminResponse)
def desativar(
    usuario_id: UUID, admin: Usuario = Depends(exige_papel("admin")), usuarios: Usuarios = Depends(get_usuarios)
) -> UsuarioAdminResponse:
    """Revoga todas as sessões da pessoa. O que ela registrou fica. 404 sem a pessoa, 422
    para a própria conta."""
    return _mudar(lambda: usuarios.desativar(admin, usuario_id))


@router.post(
    "/usuarios/{usuario_id}/reativar",
    response_model=UsuarioAdminResponse,
    dependencies=[Depends(exige_papel("admin"))],
)
def reativar(usuario_id: UUID, usuarios: Usuarios = Depends(get_usuarios)) -> UsuarioAdminResponse:
    """404 sem a pessoa."""
    return _mudar(lambda: usuarios.reativar(usuario_id))


@router.put(
    "/usuarios/{usuario_id}/senha",
    response_model=UsuarioAdminResponse,
    dependencies=[Depends(exige_papel("admin"))],
)
def redefinir_senha(
    usuario_id: UUID, corpo: RedefinirSenhaRequest, usuarios: Usuarios = Depends(get_usuarios)
) -> UsuarioAdminResponse:
    """Para quem esqueceu a senha. 404 sem a pessoa, 422 com a senha curta."""
    return _mudar(lambda: usuarios.redefinir_senha(usuario_id, corpo.senha))
