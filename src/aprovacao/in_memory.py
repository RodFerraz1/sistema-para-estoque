"""Implementação em memória da fila de aprovação, para testes."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from threading import Lock
from uuid import UUID

from src.aprovacao.repositorio import CAMPOS_DA_DECISAO, SugestoesFilaRepositorio
from src.aprovacao.schemas import StatusSugestao, SugestaoNaFila


def _ordem_da_fila(s: SugestaoNaFila) -> tuple[bool, float, str, str]:
    return (not s.destaque, s.cobertura_na_chegada_sem_compra_meses, s.sku_code, str(s.id))


def _ordem_das_decididas(s: SugestaoNaFila) -> tuple[bool, float, float, str]:
    return (
        s.decidido_em is None,
        -s.decidido_em.timestamp() if s.decidido_em else 0.0,
        -s.criado_em.timestamp(),
        str(s.id),
    )


class InMemorySugestoesFilaRepositorio(SugestoesFilaRepositorio):
    """Uma trava para a fila inteira faz o papel do `SELECT ... FOR UPDATE` do Postgres."""

    def __init__(self) -> None:
        self._sugestoes: dict[UUID, SugestaoNaFila] = {}
        self._trava = Lock()

    def substituir_pendentes(self, novas: Sequence[SugestaoNaFila]) -> int:
        with self._trava:
            pendentes = [s for s in self._sugestoes.values() if s.status == "pendente"]
            for s in pendentes:
                self._sugestoes[s.id] = s.model_copy(update={"status": "substituida"})
            for s in novas:
                self._sugestoes[s.id] = s
            return len(pendentes)

    def listar(self, status: StatusSugestao) -> list[SugestaoNaFila]:
        com_status = [s for s in self._sugestoes.values() if s.status == status]
        chave = _ordem_da_fila if status == "pendente" else _ordem_das_decididas
        return sorted(com_status, key=chave)

    def carregar(self, id: UUID) -> SugestaoNaFila | None:
        return self._sugestoes.get(id)

    def decidir(
        self, id: UUID, decisao: Callable[[SugestaoNaFila], SugestaoNaFila]
    ) -> SugestaoNaFila | None:
        with self._trava:
            atual = self._sugestoes.get(id)
            if atual is None:
                return None
            decidida = decisao(atual)
            gravada = atual.model_copy(update={campo: getattr(decidida, campo) for campo in CAMPOS_DA_DECISAO})
            self._sugestoes[id] = gravada
            return gravada
