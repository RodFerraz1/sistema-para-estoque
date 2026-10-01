"""DTOs de entrada do `ERPAdapter` que não pertencem a nenhum módulo de domínio."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ItemNovoPedido(BaseModel):
    """Item de um pedido de compra que o Copilot cria no ERP."""

    model_config = ConfigDict(frozen=True)

    sku_code: str
    quantidade: int = Field(gt=0)
    preco_unitario_centavos: int = Field(ge=0)
