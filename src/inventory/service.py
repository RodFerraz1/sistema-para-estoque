"""Módulo `inventory`: sabe sobre estoque atual e cobertura.

`cobertura_meses` depende de giro, portanto injeta `Sales`. Essa é
dependência intra-módulo explícita (documentada em module-interfaces.md).
"""
from __future__ import annotations

from src.erp_adapter.port import ERPAdapter
from src.inventory.schemas import (
    Cobertura,
    EmTransito,
    Estoque,
    ItemEmTransito,
    SKUAbaixoDoPiso,
)
from src.sales.schemas import GiroMedioMensal
from src.sales.service import Sales


def cobertura(disponivel: int, giro: GiroMedioMensal) -> Cobertura:
    if giro.unidades_por_mes == 0.0:
        return Cobertura(meses=None, sem_giro=True)
    return Cobertura(meses=disponivel / giro.unidades_por_mes, sem_giro=False)


def _em_transito(itens: list[ItemEmTransito]) -> EmTransito:
    return EmTransito(total_unidades=sum(i.quantidade_pendente for i in itens), itens=itens)


class Inventory:
    def __init__(self, erp: ERPAdapter, sales: Sales) -> None:
        self._erp = erp
        self._sales = sales

    def estoque_atual(self, sku_code: str) -> Estoque | None:
        return self._erp.estoque_de(sku_code)

    def cobertura_meses(self, sku_code: str) -> Cobertura:
        estoque = self.estoque_atual(sku_code)
        disponivel = estoque.quantidade_disponivel if estoque is not None else 0
        return cobertura(disponivel, self._sales.giro_medio_mensal(sku_code))

    def estoques(self) -> dict[str, Estoque]:
        """O estoque atual dos SKUs ativos numa leitura só. SKU sem a linha de estoque no
        ERP fica de fora."""
        return self._erp.estoques()

    def em_transito(self, sku_code: str) -> EmTransito:
        return _em_transito(self._erp.itens_em_transito_de(sku_code))

    def em_transito_por_sku(self) -> dict[str, EmTransito]:
        """`em_transito` dos SKUs ativos numa leitura só. SKU sem nada a caminho fica de fora."""
        return {codigo: _em_transito(itens) for codigo, itens in self._erp.itens_em_transito().items()}

    def abaixo_do_piso(self, dias_piso: int = 20) -> list[SKUAbaixoDoPiso]:
        """SKUs ativos com cobertura abaixo do piso, ordenados por urgência.

        Converte `dias_piso` em meses via `dias_piso / 30`. SKUs sem giro
        (cobertura indefinida) ficam de fora - sem demanda, não há alerta
        de reposição.
        """
        piso_meses = dias_piso / 30
        alertas: list[SKUAbaixoDoPiso] = []
        for sku in self._erp.listar_skus():
            cobertura = self.cobertura_meses(sku.sku_code)
            if cobertura.meses is None:
                continue
            if cobertura.meses >= piso_meses:
                continue
            alertas.append(
                SKUAbaixoDoPiso(
                    sku_id=sku.id,
                    sku_code=sku.sku_code,
                    produto_nome=sku.produto_nome,
                    cobertura_meses=cobertura.meses,
                )
            )
        alertas.sort(key=lambda a: a.cobertura_meses)
        return alertas
