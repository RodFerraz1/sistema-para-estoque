"""Port de persistência da fila de aprovação.

Ordem da fila (pendentes): destaque primeiro, depois a cobertura na chegada sem a
compra, crescente (o mais urgente primeiro), e o `sku_code` para desempatar. As
outras situações vêm da decisão mais recente para a mais antiga (as substituídas,
sem decisão, pela criação mais recente).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol
from uuid import UUID

from src.aprovacao.schemas import StatusSugestao, SugestaoNaFila

CAMPOS_DA_DECISAO = (
    "status",
    "faixa",
    "decidido_em",
    "decidido_por",
    "quantidade_aprovada",
    "justificativa",
    "motivo_rejeicao",
    "pedido_compra_id",
)


class SugestoesFilaRepositorio(Protocol):
    def substituir_pendentes(self, novas: Sequence[SugestaoNaFila]) -> int:
        """Numa transação, marca como `substituida` todas as pendentes e grava as
        `novas`. Devolve quantas pendentes foram substituídas."""
        ...

    def listar(self, status: StatusSugestao) -> list[SugestaoNaFila]: ...

    def carregar(self, id: UUID) -> SugestaoNaFila | None: ...

    def decidir(
        self, id: UUID, decisao: Callable[[SugestaoNaFila], SugestaoNaFila]
    ) -> SugestaoNaFila | None:
        """Reserva a sugestão, chama `decisao` com ela e grava os campos de decisão
        (`CAMPOS_DA_DECISAO`) do que `decisao` devolver. Enquanto a reserva dura, outra
        decisão ou substituição da mesma sugestão espera e depois a vê já decidida.
        Se `decisao` lança, nada é gravado, a reserva é solta e a exceção propaga.
        `None`, sem chamar `decisao`, quando a sugestão não existe."""
        ...
