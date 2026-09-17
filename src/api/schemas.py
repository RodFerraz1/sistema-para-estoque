"""DTOs de resposta HTTP.

Camada API compõe DTOs dos módulos em respostas amigáveis.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.inventory.schemas import Cobertura, Estoque


class GiroResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    unidades_por_mes: float
    meses_considerados: int


class FornecedorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    fornecedor_id: UUID
    fornecedor_nome: str
    preco_unitario_reais: int
    moq_unidades: int
    lead_time_dias_contratado: int
    lead_time_dias_observado: int | None


class AnaliseSKUResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_code: str
    produto_nome: str
    categoria: str
    estoque: Estoque
    giro: GiroResponse
    cobertura: Cobertura
    fornecedores: list[FornecedorResponse]
