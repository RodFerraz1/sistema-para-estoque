"""Ports de persistência do módulo `usuarios`."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.usuarios.schemas import Sessao, Usuario


class EmailJaCadastrado(ValueError):
    def __init__(self, email: str) -> None:
        super().__init__(f"Já existe uma pessoa com o e-mail {email}.")
        self.email = email


class UsuariosRepositorio(Protocol):
    def gravar(self, usuario: Usuario) -> None:
        """Lança `EmailJaCadastrado` se o e-mail já existe."""
        ...

    def por_id(self, usuario_id: UUID) -> Usuario | None: ...

    def por_email(self, email: str) -> Usuario | None: ...

    def registrar_acesso(self, usuario_id: UUID, quando: datetime) -> None: ...


class SessoesRepositorio(Protocol):
    def gravar(self, sessao: Sessao) -> None: ...

    def por_token_hash(self, token_hash: str) -> Sessao | None: ...

    def renovar(self, token_hash: str, expira_em: datetime) -> None: ...

    def revogar(self, token_hash: str, quando: datetime) -> None:
        """Não muda uma sessão já revogada."""
        ...


class TentativasLoginRepositorio(Protocol):
    """Só as tentativas erradas, para o bloqueio."""

    def registrar_falha(self, email: str, quando: datetime) -> None: ...

    def falhas_desde(self, email: str, desde: datetime) -> list[datetime]:
        """As falhas do e-mail a partir de `desde`, da mais antiga para a mais recente."""
        ...

    def limpar(self, email: str) -> None: ...
