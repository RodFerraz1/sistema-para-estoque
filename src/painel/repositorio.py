"""Ports de persistência do módulo `painel`. Avisos e decisões de compra são append-only."""
from __future__ import annotations

from typing import Protocol

from src.painel.schemas import Aviso, DecisaoCompra


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
