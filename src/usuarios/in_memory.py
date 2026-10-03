"""Implementações em memória dos repositórios do módulo `usuarios`, para testes."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.usuarios.repositorio import (
    EmailJaCadastrado,
    SessoesRepositorio,
    TentativasLoginRepositorio,
    UsuariosRepositorio,
)
from src.usuarios.schemas import Sessao, Usuario


class InMemoryUsuariosRepositorio(UsuariosRepositorio):
    def __init__(self) -> None:
        self._usuarios: dict[UUID, Usuario] = {}

    def gravar(self, usuario: Usuario) -> None:
        if self.por_email(usuario.email) is not None:
            raise EmailJaCadastrado(usuario.email)
        self._usuarios[usuario.id] = usuario

    def por_id(self, usuario_id: UUID) -> Usuario | None:
        return self._usuarios.get(usuario_id)

    def por_email(self, email: str) -> Usuario | None:
        return next((u for u in self._usuarios.values() if u.email == email), None)

    def registrar_acesso(self, usuario_id: UUID, quando: datetime) -> None:
        usuario = self._usuarios[usuario_id]
        self._usuarios[usuario_id] = usuario.model_copy(update={"ultimo_acesso_em": quando})


class InMemorySessoesRepositorio(SessoesRepositorio):
    def __init__(self) -> None:
        self._sessoes: dict[str, Sessao] = {}

    def gravar(self, sessao: Sessao) -> None:
        self._sessoes[sessao.token_hash] = sessao

    def por_token_hash(self, token_hash: str) -> Sessao | None:
        return self._sessoes.get(token_hash)

    def renovar(self, token_hash: str, expira_em: datetime) -> None:
        sessao = self._sessoes[token_hash]
        self._sessoes[token_hash] = sessao.model_copy(update={"expira_em": expira_em})

    def revogar(self, token_hash: str, quando: datetime) -> None:
        sessao = self._sessoes.get(token_hash)
        if sessao is not None and sessao.revogada_em is None:
            self._sessoes[token_hash] = sessao.model_copy(update={"revogada_em": quando})


class InMemoryTentativasLoginRepositorio(TentativasLoginRepositorio):
    def __init__(self) -> None:
        self._falhas: list[tuple[str, datetime]] = []

    def registrar_falha(self, email: str, quando: datetime) -> None:
        self._falhas.append((email, quando))

    def falhas_desde(self, email: str, desde: datetime) -> list[datetime]:
        return sorted(q for e, q in self._falhas if e == email and q >= desde)

    def limpar(self, email: str) -> None:
        self._falhas = [(e, q) for e, q in self._falhas if e != email]
