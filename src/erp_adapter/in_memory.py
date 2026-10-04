"""Implementação em memória do `ERPAdapter`, apenas para testes.

Aceita DTOs de domínio e serve leituras filtradas. `Estoque` e
`FornecedorParaSKU` não carregam o SKU, então chegam indexados por
`sku_code`; vínculo inativo é representado pela ausência na lista. Não
valida consistência entre coleções: é responsabilidade do teste montar
dados coerentes.

`PedidoCompra` e `ItemPedidoCompra` espelham as linhas de
`erp.pedidos_compra` e `erp.pedidos_compra_itens`. Não são DTOs de domínio:
alimentam as leituras de pedido.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from collections.abc import Callable, Iterator
from typing import cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import ItemDePedido, StatusPedidoCompra
from src.inventory.schemas import (
    STATUS_EM_TRANSITO,
    Estoque,
    ItemEmTransito,
    Movimentacao,
    StatusEmTransito,
)
from src.sales.schemas import Venda, VendasDoDia, VendasDoMes


class PedidoCompra(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    fornecedor_id: UUID
    status: StatusPedidoCompra
    data_prevista_entrega: date | None
    criado_em: datetime


class ItemPedidoCompra(BaseModel):
    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    sku_id: UUID
    quantidade: int
    quantidade_recebida: int
    preco_unitario_centavos: int = 0


class InMemoryERPAdapter(ERPAdapter):
    def __init__(
        self,
        *,
        skus: list[SKU] | None = None,
        fornecedores: list[Fornecedor] | None = None,
        fornecedores_por_sku: dict[str, list[FornecedorParaSKU]] | None = None,
        estoques: dict[str, Estoque] | None = None,
        movimentacoes: list[Movimentacao] | None = None,
        vendas: list[Venda] | None = None,
        pedidos_compra: list[PedidoCompra] | None = None,
        itens_pedido_compra: list[ItemPedidoCompra] | None = None,
    ) -> None:
        self.skus: list[SKU] = list(skus or [])
        self.fornecedores: list[Fornecedor] = list(fornecedores or [])
        self.vinculos: dict[str, list[FornecedorParaSKU]] = dict(
            fornecedores_por_sku or {}
        )
        self.estoques_por_sku: dict[str, Estoque] = dict(estoques or {})
        self.movimentacoes: list[Movimentacao] = list(movimentacoes or [])
        self.vendas: list[Venda] = list(vendas or [])
        self.pedidos_compra: list[PedidoCompra] = list(pedidos_compra or [])
        self.itens_pedido_compra: list[ItemPedidoCompra] = list(
            itens_pedido_compra or []
        )

    def _sku_id(self, sku_code: str) -> UUID | None:
        return next((s.id for s in self.skus if s.sku_code == sku_code), None)

    def carregar_sku(self, sku_code: str) -> SKU | None:
        return next((s for s in self.skus if s.sku_code == sku_code), None)

    def listar_skus(self) -> list[SKU]:
        return sorted((s for s in self.skus if s.ativo), key=lambda s: s.sku_code)

    def carregar_fornecedor(self, fornecedor_id: UUID) -> Fornecedor | None:
        return next((f for f in self.fornecedores if f.id == fornecedor_id), None)

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        ativos_ids = {f.id for f in self.fornecedores if f.ativo}
        return sorted(
            (
                f
                for f in self.vinculos.get(sku_code, [])
                if f.fornecedor_id in ativos_ids
            ),
            key=lambda f: f.preco_unitario_reais,
        )

    def estoque_de(self, sku_code: str) -> Estoque | None:
        return self.estoques_por_sku.get(sku_code)

    def vendas_de(self, sku_code: str, desde: datetime) -> list[Venda]:
        sku_id = self._sku_id(sku_code)
        return sorted(
            (v for v in self.vendas if v.sku_id == sku_id and v.data >= desde),
            key=lambda v: v.data,
        )

    def movimentacoes_de(
        self, sku_code: str, desde: datetime
    ) -> list[Movimentacao]:
        sku_id = self._sku_id(sku_code)
        return sorted(
            (m for m in self.movimentacoes if m.sku_id == sku_id and m.data >= desde),
            key=lambda m: m.data,
        )

    def itens_em_transito_de(self, sku_code: str) -> list[ItemEmTransito]:
        sku_id = self._sku_id(sku_code)
        if sku_id is None:
            return []
        return self._em_transito(lambda i: i.sku_id == sku_id).get(sku_id, [])

    def _em_transito(self, filtro: Callable[[ItemPedidoCompra], bool]) -> dict[UUID, list[ItemEmTransito]]:
        pedidos = {
            p.id: p for p in self.pedidos_compra if p.status in STATUS_EM_TRANSITO
        }
        por_sku: dict[UUID, list[ItemEmTransito]] = defaultdict(list)
        for i in self.itens_pedido_compra:
            pedido = pedidos.get(i.pedido_id)
            if pedido is None or i.quantidade <= i.quantidade_recebida or not filtro(i):
                continue
            por_sku[i.sku_id].append(
                ItemEmTransito(
                    pedido_id=pedido.id,
                    fornecedor_id=pedido.fornecedor_id,
                    status=cast(StatusEmTransito, pedido.status),
                    quantidade_pendente=i.quantidade - i.quantidade_recebida,
                    data_prevista_entrega=pedido.data_prevista_entrega,
                )
            )
        for itens in por_sku.values():
            itens.sort(
                key=lambda i: (
                    i.data_prevista_entrega is None,
                    i.data_prevista_entrega or date.min,
                    i.pedido_id,
                )
            )
        return por_sku

    def itens_de_pedido_de(self, sku_code: str) -> list[ItemDePedido]:
        sku_id = self._sku_id(sku_code)
        pedidos = {p.id: p for p in self.pedidos_compra}
        nomes = {f.id: f.nome for f in self.fornecedores}
        itens = [
            ItemDePedido(
                pedido_id=pedido.id,
                criado_em=pedido.criado_em,
                fornecedor_id=pedido.fornecedor_id,
                fornecedor_nome=nomes[pedido.fornecedor_id],
                status=pedido.status,
                quantidade=i.quantidade,
                preco_unitario_centavos=i.preco_unitario_centavos,
            )
            for i in self.itens_pedido_compra
            if i.sku_id == sku_id and (pedido := pedidos.get(i.pedido_id)) is not None
        ]
        return sorted(itens, key=lambda i: (i.criado_em, str(i.pedido_id)), reverse=True)

    def _ativos(self) -> dict[UUID, str]:
        return {s.id: s.sku_code for s in self.skus if s.ativo}

    def estoques(self) -> dict[str, Estoque]:
        ativos = set(self._ativos().values())
        return {codigo: e for codigo, e in self.estoques_por_sku.items() if codigo in ativos}

    def giros(self, desde: datetime) -> dict[str, list[VendasDoMes]]:
        somas: dict[str, dict[tuple[int, int], list[Venda]]] = defaultdict(lambda: defaultdict(list))
        for codigo, venda in self._vendas_ativas(desde):
            data = venda.data.astimezone(UTC)
            somas[codigo][(data.year, data.month)].append(venda)
        return {
            codigo: [
                VendasDoMes(
                    ano=ano,
                    mes=mes,
                    quantidade=sum(v.quantidade for v in vendas),
                    primeira_venda=min(v.data for v in vendas),
                )
                for (ano, mes), vendas in sorted(meses.items())
            ]
            for codigo, meses in somas.items()
        }

    def vendas_diarias(self, desde: datetime) -> dict[str, list[VendasDoDia]]:
        somas: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
        for codigo, venda in self._vendas_ativas(desde):
            somas[codigo][venda.data.astimezone(UTC).date()] += venda.quantidade
        return {
            codigo: [VendasDoDia(dia=dia, quantidade=q) for dia, q in sorted(dias.items())]
            for codigo, dias in somas.items()
        }

    def _vendas_ativas(self, desde: datetime) -> Iterator[tuple[str, Venda]]:
        ativos = self._ativos()
        for venda in self.vendas:
            if venda.sku_id in ativos and venda.data >= desde:
                yield ativos[venda.sku_id], venda

    def fornecedores_por_sku(self) -> dict[str, list[FornecedorParaSKU]]:
        por_sku = {codigo: self.fornecedores_de(codigo) for codigo in self._ativos().values()}
        return {codigo: lista for codigo, lista in por_sku.items() if lista}

    def itens_em_transito(self) -> dict[str, list[ItemEmTransito]]:
        ativos = self._ativos()
        return {ativos[sku_id]: itens for sku_id, itens in self._em_transito(lambda i: i.sku_id in ativos).items()}
