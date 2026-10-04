"""Ports de persistência do módulo `painel`. Avisos, decisões de compra e cobranças de
entrega são append-only."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.painel.schemas import Aviso, CobrancaEntrega, DecisaoCompra


class AvisosRepositorio(Protocol):
    def gravar(self, aviso: Aviso) -> None: ...

    def listar(self, sku_code: str | None = None) -> list[Aviso]:
        """Os avisos do SKU, ou de todos sem `sku_code`, do mais recente para o mais
        antigo (o `id` desempata)."""
        ...


class DecisoesRepositorio(Protocol):
    def gravar(self, decisao: DecisaoCompra) -> None: ...

    def listar(self, sku_code: str) -> list[DecisaoCompra]:
        """As decisões do SKU, da mais recente para a mais antiga (o `id` desempata)."""
        ...

    def ultimas(self) -> dict[str, DecisaoCompra]:
        """A decisão mais recente de cada SKU que tem alguma, pelo `sku_code`."""
        ...


class CobrancasRepositorio(Protocol):
    def gravar(self, cobranca: CobrancaEntrega) -> None: ...

    def listar(self, pedido_id: UUID) -> list[CobrancaEntrega]:
        """As cobranças do pedido, da mais recente para a mais antiga (o `id` desempata)."""
        ...

    def ultimas(self) -> dict[UUID, CobrancaEntrega]:
        """A cobrança mais recente de cada pedido que tem alguma, pelo `pedido_id`."""
        ...
