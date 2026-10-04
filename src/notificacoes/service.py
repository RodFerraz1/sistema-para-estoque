"""Módulo `notificacoes`: os episódios de alerta e o que cada usuário vê deles.

Um episódio é o intervalo em que uma condição vale (um SKU em ruptura, um pedido com
entrega atrasada). A varredura compara as condições de agora com os episódios abertos:
abre as novas e fecha as que deixaram de valer, então a mesma condição notifica uma vez
enquanto dura e de novo se voltar. Quem sabe as condições é o módulo dono delas (o
`painel`, para o comprador); este módulo só guarda os episódios. Eventos de uma vez só,
como o aviso da equipe de vendas, nascem fechados na hora em que acontecem.

Notificação é o episódio visto por um usuário do papel de destino ou, quando o episódio é
dirigido a uma pessoa (a decisão sobre o aviso de uma vendedora), só por ela. Não lida é a aberta
depois do cursor `notificacoes_vistas_ate` do usuário. Não há agendador: as varreduras
rodam quando alguém abre o Copilot.
"""
from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import UTC, datetime
from uuid import uuid4

from src.notificacoes.repositorio import EpisodiosRepositorio
from src.notificacoes.schemas import CaixaDeNotificacoes, Condicao, Episodio, Notificacao, TipoEpisodio
from src.usuarios.repositorio import UsuariosRepositorio
from src.usuarios.schemas import Usuario

Relogio = Callable[[], datetime]

TAMANHO_DA_LISTA = 50


def agora_utc() -> datetime:
    return datetime.now(UTC)


class Notificacoes:
    def __init__(
        self, episodios: EpisodiosRepositorio, usuarios: UsuariosRepositorio, *, relogio: Relogio = agora_utc
    ) -> None:
        self._episodios = episodios
        self._usuarios = usuarios
        self._relogio = relogio

    def varrer(self, tipos: Collection[TipoEpisodio], condicoes: list[Condicao]) -> None:
        """Abre e fecha os episódios dos `tipos` pelas `condicoes` de agora."""
        self._episodios.varrer(tipos, condicoes, self._relogio())

    def registrar(self, evento: Condicao, quando: datetime) -> Episodio:
        """Um evento de uma vez só, que notifica sempre, sem esperar a varredura."""
        episodio = Episodio(id=uuid4(), aberto_em=quando, fechado_em=quando, **evento.model_dump())
        self._episodios.gravar(episodio)
        return episodio

    def caixa(self, usuario: Usuario) -> CaixaDeNotificacoes:
        """As notificações dirigidas ao usuário e as dos papéis dele, as mais recentes
        primeiro (no máximo `TAMANHO_DA_LISTA`), e o total de não lidas."""
        cursor = usuario.notificacoes_vistas_ate
        episodios = self._episodios.do_usuario(usuario.id, usuario.papeis, TAMANHO_DA_LISTA)
        return CaixaDeNotificacoes(
            notificacoes=[
                Notificacao(episodio=e, lida=cursor is not None and e.aberto_em <= cursor) for e in episodios
            ],
            nao_lidas=self._episodios.abertos_depois(usuario.id, usuario.papeis, cursor),
        )

    def marcar_vistas(self, usuario: Usuario) -> None:
        """Marca como lidas todas as notificações abertas até agora."""
        self._usuarios.marcar_notificacoes_vistas(usuario.id, self._relogio())
