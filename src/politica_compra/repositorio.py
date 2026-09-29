"""Port de persistência da política de compra.

Append-only: cada edição grava uma versão nova e a ativa é a de maior
`versao`. Não existe atualizar nem apagar versão.
"""
from __future__ import annotations

from typing import Protocol

from src.politica_compra.schemas import ParametrosPolitica, PoliticaCompra


class PoliticaCompraRepositorio(Protocol):
    def ativa(self) -> PoliticaCompra: ...

    def salvar_nova_versao(self, parametros: ParametrosPolitica) -> PoliticaCompra: ...
