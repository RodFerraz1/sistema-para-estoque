"""Implementação em memória do repositório do módulo `notificacoes`, para testes."""
from __future__ import annotations

import threading
from collections.abc import Collection
from datetime import datetime
from uuid import UUID, uuid4

from src.notificacoes.repositorio import EpisodiosRepositorio, a_abrir_e_a_fechar
from src.notificacoes.schemas import Condicao, Episodio, TipoEpisodio
from src.usuarios.schemas import Papel


class InMemoryEpisodiosRepositorio(EpisodiosRepositorio):
    def __init__(self) -> None:
        self._episodios: list[Episodio] = []
        self._trava = threading.Lock()

    def varrer(self, tipos: Collection[TipoEpisodio], condicoes: list[Condicao], agora: datetime) -> None:
        with self._trava:
            abertos = [e for e in self._episodios if e.fechado_em is None and e.tipo in tipos]
            novas, a_fechar = a_abrir_e_a_fechar(abertos, [c for c in condicoes if c.tipo in tipos])
            fechar = {e.id for e in a_fechar}
            self._episodios = [
                e.model_copy(update={"fechado_em": agora}) if e.id in fechar else e for e in self._episodios
            ]
            self._episodios.extend(
                Episodio(id=uuid4(), aberto_em=agora, fechado_em=None, **c.model_dump()) for c in novas
            )

    def gravar(self, episodio: Episodio) -> None:
        with self._trava:
            self._episodios.append(episodio)

    def _do_usuario(self, usuario_id: UUID, papeis: Collection[Papel]) -> list[Episodio]:
        return [
            e
            for e in self._episodios
            if e.usuario_destino == usuario_id or (e.usuario_destino is None and e.papel_destino in papeis)
        ]

    def do_usuario(self, usuario_id: UUID, papeis: Collection[Papel], limite: int) -> list[Episodio]:
        episodios = self._do_usuario(usuario_id, papeis)
        return sorted(episodios, key=lambda e: (e.aberto_em, str(e.id)), reverse=True)[:limite]

    def abertos_depois(self, usuario_id: UUID, papeis: Collection[Papel], desde: datetime | None) -> int:
        return sum(1 for e in self._do_usuario(usuario_id, papeis) if desde is None or e.aberto_em > desde)
