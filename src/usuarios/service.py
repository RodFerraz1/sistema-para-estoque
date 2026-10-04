"""Módulo `usuarios`: login com e-mail e senha, sessão e papéis (ADR-0007).

A senha é guardada com argon2id. A sessão é um token aleatório que vai no cookie; só o
hash dele fica no banco. Ela vale `DURACAO_DA_SESSAO` desde o último uso e é renovada a
cada uso. `MAXIMO_DE_FALHAS` tentativas erradas para o mesmo e-mail dentro de
`JANELA_DE_FALHAS` bloqueiam esse e-mail por `DURACAO_DO_BLOQUEIO`. Tentativa durante o
bloqueio não conta, para o bloqueio não se estender sozinho.
"""
from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from src.usuarios.repositorio import SessoesRepositorio, TentativasLoginRepositorio, UsuariosRepositorio
from src.usuarios.schemas import PAPEIS, Papel, Sessao, Usuario

Relogio = Callable[[], datetime]

DURACAO_DA_SESSAO = timedelta(days=30)
MAXIMO_DE_FALHAS = 5
JANELA_DE_FALHAS = timedelta(minutes=15)
DURACAO_DO_BLOQUEIO = timedelta(minutes=15)
TAMANHO_MINIMO_DA_SENHA = 8

_hasher = PasswordHasher()
# Verificado quando o e-mail não existe, para a resposta levar o mesmo tempo.
_HASH_DE_NINGUEM = _hasher.hash(secrets.token_urlsafe(16))


def agora_utc() -> datetime:
    return datetime.now(UTC)


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class CredenciaisInvalidas(Exception):
    def __init__(self) -> None:
        super().__init__("E-mail ou senha incorretos.")


class LoginBloqueado(Exception):
    def __init__(self, ate: datetime) -> None:
        super().__init__("Muitas tentativas erradas. Espere 15 minutos e tente de novo.")
        self.ate = ate


class DadosInvalidos(ValueError):
    pass


class UsuarioNaoEncontrado(LookupError):
    def __init__(self) -> None:
        super().__init__("Pessoa não encontrada.")


class SenhaAtualErrada(ValueError):
    def __init__(self) -> None:
        super().__init__("A senha atual não confere.")


class Usuarios:
    def __init__(
        self,
        usuarios: UsuariosRepositorio,
        sessoes: SessoesRepositorio,
        tentativas: TentativasLoginRepositorio,
        *,
        relogio: Relogio = agora_utc,
    ) -> None:
        self._usuarios = usuarios
        self._sessoes = sessoes
        self._tentativas = tentativas
        self._relogio = relogio

    def criar(self, nome: str, email: str, senha: str, papeis: list[Papel]) -> Usuario:
        """Lança `DadosInvalidos` sem nome, sem e-mail, com senha curta ou sem papel, e
        `EmailJaCadastrado` com e-mail repetido."""
        nome, email = nome.strip(), normalizar_email(email)
        if not nome:
            raise DadosInvalidos("Informe o nome.")
        if "@" not in email:
            raise DadosInvalidos("Informe um e-mail válido.")
        usuario = Usuario(
            id=uuid4(),
            nome=nome,
            email=email,
            senha_hash=_hash_da_senha(senha),
            papeis=_papeis(papeis),
            ativo=True,
            criado_em=self._relogio(),
            ultimo_acesso_em=None,
        )
        self._usuarios.gravar(usuario)
        return usuario

    def listar(self) -> list[Usuario]:
        return self._usuarios.listar()

    def mudar_papeis(self, admin: Usuario, usuario_id: UUID, papeis: list[Papel]) -> Usuario:
        """Lança `UsuarioNaoEncontrado` e `DadosInvalidos` sem papel ou quando o admin tira
        o próprio papel de admin."""
        usuario = self._por_id(usuario_id)
        if usuario.id == admin.id and "admin" not in papeis:
            raise DadosInvalidos("Você não pode tirar o seu próprio papel de admin.")
        return self._atualizar(usuario, papeis=_papeis(papeis))

    def desativar(self, admin: Usuario, usuario_id: UUID) -> Usuario:
        """A pessoa não entra mais e todas as sessões dela são revogadas. O que ela
        registrou fica. Lança `UsuarioNaoEncontrado` e `DadosInvalidos` para o próprio admin."""
        usuario = self._por_id(usuario_id)
        if usuario.id == admin.id:
            raise DadosInvalidos("Você não pode desativar a sua própria conta.")
        self._sessoes.revogar_do_usuario(usuario.id, self._relogio())
        return self._atualizar(usuario, ativo=False)

    def reativar(self, usuario_id: UUID) -> Usuario:
        return self._atualizar(self._por_id(usuario_id), ativo=True)

    def redefinir_senha(self, usuario_id: UUID, senha: str) -> Usuario:
        """Para quem esqueceu a senha. Lança `UsuarioNaoEncontrado` e `DadosInvalidos`
        com senha curta."""
        return self._atualizar(self._por_id(usuario_id), senha_hash=_hash_da_senha(senha))

    def trocar_senha(self, usuario: Usuario, senha_atual: str, nova_senha: str) -> Usuario:
        """Lança `SenhaAtualErrada` e `DadosInvalidos` com a nova senha curta."""
        if not _senha_confere(usuario.senha_hash, senha_atual):
            raise SenhaAtualErrada()
        return self._atualizar(usuario, senha_hash=_hash_da_senha(nova_senha))

    def _por_id(self, usuario_id: UUID) -> Usuario:
        usuario = self._usuarios.por_id(usuario_id)
        if usuario is None:
            raise UsuarioNaoEncontrado()
        return usuario

    def _atualizar(self, usuario: Usuario, **mudancas: object) -> Usuario:
        atualizado = usuario.model_copy(update=mudancas)
        self._usuarios.atualizar(atualizado)
        return atualizado

    def entrar(self, email: str, senha: str) -> tuple[Usuario, str]:
        """Abre uma sessão e devolve o usuário e o token do cookie. Lança `LoginBloqueado`
        ou `CredenciaisInvalidas` (e-mail desconhecido, senha errada ou usuário inativo)."""
        email = normalizar_email(email)
        agora = self._relogio()
        bloqueio = self._bloqueado_ate(email, agora)
        if bloqueio is not None:
            raise LoginBloqueado(bloqueio)
        usuario = self._usuarios.por_email(email)
        if not _senha_confere(usuario.senha_hash if usuario else _HASH_DE_NINGUEM, senha) or not (
            usuario and usuario.ativo
        ):
            self._tentativas.registrar_falha(email, agora)
            raise CredenciaisInvalidas()
        self._tentativas.limpar(email)
        token = secrets.token_urlsafe(32)
        self._sessoes.gravar(
            Sessao(
                token_hash=hash_do_token(token),
                usuario_id=usuario.id,
                criada_em=agora,
                expira_em=agora + DURACAO_DA_SESSAO,
                revogada_em=None,
            )
        )
        self._usuarios.registrar_acesso(usuario.id, agora)
        return usuario, token

    def usuario_da_sessao(self, token: str) -> Usuario | None:
        """O dono da sessão, se ela está aberta e ele ativo. Renova a sessão."""
        token_hash = hash_do_token(token)
        sessao = self._sessoes.por_token_hash(token_hash)
        agora = self._relogio()
        if sessao is None or sessao.revogada_em is not None or sessao.expira_em <= agora:
            return None
        usuario = self._usuarios.por_id(sessao.usuario_id)
        if usuario is None or not usuario.ativo:
            return None
        self._sessoes.renovar(token_hash, agora + DURACAO_DA_SESSAO)
        self._usuarios.registrar_acesso(usuario.id, agora)
        return usuario

    def sair(self, token: str) -> None:
        self._sessoes.revogar(hash_do_token(token), self._relogio())

    def _bloqueado_ate(self, email: str, agora: datetime) -> datetime | None:
        falhas = self._tentativas.falhas_desde(email, agora - JANELA_DE_FALHAS - DURACAO_DO_BLOQUEIO)
        fins = [
            falhas[i] + DURACAO_DO_BLOQUEIO
            for i in range(MAXIMO_DE_FALHAS - 1, len(falhas))
            if falhas[i] - falhas[i - MAXIMO_DE_FALHAS + 1] <= JANELA_DE_FALHAS
        ]
        return max((f for f in fins if f > agora), default=None)


def _hash_da_senha(senha: str) -> str:
    if len(senha) < TAMANHO_MINIMO_DA_SENHA:
        raise DadosInvalidos(f"A senha precisa ter pelo menos {TAMANHO_MINIMO_DA_SENHA} caracteres.")
    return _hasher.hash(senha)


def _papeis(papeis: list[Papel]) -> list[Papel]:
    if not papeis:
        raise DadosInvalidos("Escolha pelo menos um papel.")
    return [p for p in PAPEIS if p in papeis]


def _senha_confere(senha_hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False
