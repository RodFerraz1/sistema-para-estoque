"""DTOs do `ERPAdapter` que não pertencem a nenhum módulo de domínio: pedido de compra
não tem módulo de leitura próprio."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

StatusPedidoCompra = Literal[
    "rascunho",
    "aprovado",
    "enviado",
    "recebido_parcial",
    "recebido_total",
    "cancelado",
]


class ItemDePedido(BaseModel):
    """Item de pedido de compra de um SKU com o cabeçalho do pedido. `criado_em` é a
    data do pedido e o preço é o pago naquele pedido, em centavos."""

    model_config = ConfigDict(frozen=True)

    pedido_id: UUID
    criado_em: datetime
    fornecedor_id: UUID
    fornecedor_nome: str
    status: StatusPedidoCompra
    quantidade: int
    preco_unitario_centavos: int
