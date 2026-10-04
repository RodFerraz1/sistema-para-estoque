from __future__ import annotations

from fastapi import Depends

from src.db.engine import get_engine
from src.notificacoes.postgres import PostgresEpisodiosRepositorio
from src.notificacoes.repositorio import EpisodiosRepositorio
from src.notificacoes.service import Notificacoes, Relogio, agora_utc
from src.usuarios.dependencies import get_usuarios_repositorio
from src.usuarios.repositorio import UsuariosRepositorio


def get_episodios_repositorio() -> EpisodiosRepositorio:
    return PostgresEpisodiosRepositorio(get_engine())


def get_relogio() -> Relogio:
    """Em testes, sobrescreva para controlar a hora das varreduras e do cursor."""
    return agora_utc


def get_notificacoes(
    episodios: EpisodiosRepositorio = Depends(get_episodios_repositorio),
    usuarios: UsuariosRepositorio = Depends(get_usuarios_repositorio),
    relogio: Relogio = Depends(get_relogio),
) -> Notificacoes:
    return Notificacoes(episodios, usuarios, relogio=relogio)
