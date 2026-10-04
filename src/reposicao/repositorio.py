"""Port de persistência do módulo `reposicao`. As verificações de gôndola são append-only."""
from __future__ import annotations

from typing import Protocol

from src.reposicao.schemas import VerificacaoGondola


class VerificacoesRepositorio(Protocol):
    def gravar(self, verificacao: VerificacaoGondola) -> None: ...

    def listar(self, sku_code: str) -> list[VerificacaoGondola]:
        """As verificações do SKU, da mais recente para a mais antiga (o `id` desempata)."""
        ...

    def ultimas(self) -> dict[str, VerificacaoGondola]:
        """A verificação mais recente de cada SKU que tem alguma, pelo `sku_code`."""
        ...
