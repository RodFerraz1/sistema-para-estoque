"""Port de persistência do módulo `notificacoes`."""
from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Protocol

from src.notificacoes.schemas import Condicao, Episodio, TipoEpisodio
from src.usuarios.schemas import Papel


class EpisodiosRepositorio(Protocol):
    def varrer(self, tipos: Collection[TipoEpisodio], condicoes: list[Condicao], agora: datetime) -> None:
        """Compara as `condicoes` com os episódios abertos dos `tipos`: abre, em `agora`, as
        condições sem episódio aberto e fecha os episódios cuja condição deixou de valer.
        Idempotente e seguro com duas varreduras ao mesmo tempo: nunca há dois episódios
        abertos da mesma condição."""
        ...

    def gravar(self, episodio: Episodio) -> None:
        """Grava um evento de uma vez só, já fechado, fora da varredura."""
        ...

    def dos_papeis(self, papeis: Collection[Papel], limite: int) -> list[Episodio]:
        """Os episódios dos `papeis`, abertos ou fechados, do mais recente para o mais
        antigo (o `id` desempata), no máximo `limite`."""
        ...

    def abertos_depois(self, papeis: Collection[Papel], desde: datetime | None) -> int:
        """Quantos episódios dos `papeis` foram abertos depois de `desde` (todos sem ele)."""
        ...


def a_abrir_e_a_fechar(abertos: list[Episodio], condicoes: list[Condicao]) -> tuple[list[Condicao], list[Episodio]]:
    """As condições sem episódio aberto e os episódios abertos sem condição, para as duas
    implementações da varredura."""
    chaves_abertas = {e.chave for e in abertos}
    chaves_atuais = {c.chave for c in condicoes}
    novas: dict[tuple, Condicao] = {}
    for condicao in condicoes:
        if condicao.chave not in chaves_abertas:
            novas.setdefault(condicao.chave, condicao)
    return list(novas.values()), [e for e in abertos if e.chave not in chaves_atuais]
