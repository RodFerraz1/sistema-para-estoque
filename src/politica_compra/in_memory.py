"""Implementação em memória do `PoliticaCompraRepositorio`, para testes.

Nasce com a v1 padrão, como o banco depois das migrations, ou com a v1 que o teste passar.
"""
from __future__ import annotations

from datetime import UTC, datetime

from src.politica_compra.repositorio import PoliticaCompraRepositorio
from src.politica_compra.schemas import (
    PARAMETROS_V1,
    ParametrosPolitica,
    PoliticaCompra,
)


class InMemoryPoliticaCompraRepositorio(PoliticaCompraRepositorio):
    def __init__(self, *, now: datetime | None = None, v1: ParametrosPolitica = PARAMETROS_V1) -> None:
        self._now = now
        self._versoes: list[PoliticaCompra] = []
        self.salvar_nova_versao(v1)

    def ativa(self) -> PoliticaCompra:
        return self._versoes[-1]

    def salvar_nova_versao(self, parametros: ParametrosPolitica) -> PoliticaCompra:
        politica = PoliticaCompra(
            versao=len(self._versoes) + 1,
            criada_em=self._now or datetime.now(UTC),
            parametros=parametros,
        )
        self._versoes.append(politica)
        return politica

    def versao(self, versao: int) -> PoliticaCompra | None:
        if 1 <= versao <= len(self._versoes):
            return self._versoes[versao - 1]
        return None
