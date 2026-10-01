"""Port de persistência da fila de aprovação.

Ordem da fila (pendentes): destaque primeiro, depois a cobertura na chegada sem a
compra, crescente (o mais urgente primeiro), e o `sku_code` para desempatar. As
outras situações vêm da decisão mais recente para a mais antiga (as substituídas,
sem decisão, pela criação mais recente).
"""
from __future__ import annotations

from collections.abc import Sequence
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


class SugestoesFila(Protocol):
    def substituir_pendentes(self, novas: Sequence[SugestaoNaFila]) -> int:
        """Numa transação, marca como `substituida` todas as pendentes e grava as
        `novas`. Devolve quantas pendentes foram substituídas."""
        ...

    def listar(self, status: StatusSugestao) -> list[SugestaoNaFila]: ...

    def carregar(self, id: UUID) -> SugestaoNaFila | None: ...

    def registrar_decisao(self, decidida: SugestaoNaFila) -> bool:
        """Grava o status, a faixa e os campos de decisão de `decidida` se a sugestão
        ainda está pendente. `False` quando ela não existe ou já saiu da fila."""
        ...
