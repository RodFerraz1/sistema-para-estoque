"""Implementações em memória dos repositórios do módulo `painel`, para testes."""
from __future__ import annotations

from uuid import UUID

from src.painel.repositorio import AvisosRepositorio, CobrancasRepositorio, DecisoesRepositorio
from src.painel.schemas import Aviso, CobrancaEntrega, DecisaoCompra


class InMemoryAvisosRepositorio(AvisosRepositorio):
    def __init__(self) -> None:
        self._avisos: list[Aviso] = []

    def gravar(self, aviso: Aviso) -> None:
        self._avisos.append(aviso)

    def listar(self, sku_code: str | None = None) -> list[Aviso]:
        do_sku = [a for a in self._avisos if sku_code is None or a.sku_code == sku_code]
        return sorted(do_sku, key=lambda a: (a.criado_em, str(a.id)), reverse=True)


class InMemoryDecisoesRepositorio(DecisoesRepositorio):
    def __init__(self) -> None:
        self._decisoes: list[DecisaoCompra] = []

    def gravar(self, decisao: DecisaoCompra) -> None:
        self._decisoes.append(decisao)

    def listar(self, sku_code: str) -> list[DecisaoCompra]:
        do_sku = [d for d in self._decisoes if d.sku_code == sku_code]
        return sorted(do_sku, key=lambda d: (d.criado_em, str(d.id)), reverse=True)

    def ultimas(self) -> dict[str, DecisaoCompra]:
        return {sku_code: self.listar(sku_code)[0] for sku_code in {d.sku_code for d in self._decisoes}}


class InMemoryCobrancasRepositorio(CobrancasRepositorio):
    def __init__(self) -> None:
        self._cobrancas: list[CobrancaEntrega] = []

    def gravar(self, cobranca: CobrancaEntrega) -> None:
        self._cobrancas.append(cobranca)

    def listar(self, pedido_id: UUID) -> list[CobrancaEntrega]:
        do_pedido = [c for c in self._cobrancas if c.pedido_id == pedido_id]
        return sorted(do_pedido, key=lambda c: (c.criado_em, str(c.id)), reverse=True)

    def ultimas(self) -> dict[UUID, CobrancaEntrega]:
        return {pedido_id: self.listar(pedido_id)[0] for pedido_id in {c.pedido_id for c in self._cobrancas}}
