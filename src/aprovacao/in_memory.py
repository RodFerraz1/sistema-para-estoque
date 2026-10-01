"""Implementação em memória da fila de aprovação, para testes."""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from src.aprovacao.repositorio import CAMPOS_DA_DECISAO, SugestoesFila
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


class InMemorySugestoesFila(SugestoesFila):
    def __init__(self) -> None:
        self._sugestoes: dict[UUID, SugestaoNaFila] = {}

    def substituir_pendentes(self, novas: Sequence[SugestaoNaFila]) -> int:
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

    def registrar_decisao(self, decidida: SugestaoNaFila) -> bool:
        atual = self._sugestoes.get(decidida.id)
        if atual is None or atual.status != "pendente":
            return False
        self._sugestoes[decidida.id] = atual.model_copy(
            update={campo: getattr(decidida, campo) for campo in CAMPOS_DA_DECISAO}
        )
        return True
