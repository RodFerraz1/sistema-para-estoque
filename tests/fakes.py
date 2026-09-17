"""Fábricas de raws para montar `InMemoryERPAdapter` em testes.

Mantém defaults sensatos para que cada teste especifique apenas o que
importa. UUIDs são derivados por `uuid5` a partir do nome/código para
serem estáveis entre runs.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from src.erp_adapter.schemas import (
    EstoqueRaw,
    FornecedorRaw,
    FornecedorSKURaw,
    MovimentacaoRaw,
    SKURaw,
    VendaRaw,
)


_NS = uuid.UUID("00000000-0000-0000-0000-000000000fff")


def uid(kind: str, key: str) -> UUID:
    return uuid.uuid5(_NS, f"{kind}:{key}")


def make_sku(
    sku_code: str = "TESTE-001",
    *,
    produto_nome: str = "Produto Teste",
    categoria: str = "felpudo",
    cor: str = "branco",
    tamanho: str = "70x140",
    gramatura: int | None = 400,
    material: str | None = "algodão 100%",
    ativo: bool = True,
) -> SKURaw:
    return SKURaw(
        id=uid("sku", sku_code),
        produto_id=uid("produto", produto_nome),
        sku_code=sku_code,
        cor=cor,
        tamanho=tamanho,
        gramatura=gramatura,
        material=material,
        ativo=ativo,
        produto_nome=produto_nome,
        produto_categoria=categoria,
    )


def make_fornecedor(
    nome: str = "Katrina Têxtil",
    *,
    lead_time_dias_contratado: int = 30,
    pedido_minimo_reais: int = 10_000,
    ativo: bool = True,
) -> FornecedorRaw:
    return FornecedorRaw(
        id=uid("fornecedor", nome),
        nome=nome,
        cnpj="00.000.000/0001-00",
        prazo_pagamento_padrao="30/60",
        pedido_minimo_reais=pedido_minimo_reais,
        lead_time_dias_contratado=lead_time_dias_contratado,
        ativo=ativo,
    )


def make_fornecedor_sku(
    sku: SKURaw,
    fornecedor: FornecedorRaw,
    *,
    preco_unitario_atual: int = 2000,
    moq_unidades: int = 48,
    lead_time_dias_observado: int | None = 35,
    ativo: bool = True,
) -> FornecedorSKURaw:
    return FornecedorSKURaw(
        fornecedor_id=fornecedor.id,
        sku_id=sku.id,
        fornecedor_nome=fornecedor.nome,
        preco_unitario_atual=preco_unitario_atual,
        moq_unidades=moq_unidades,
        lead_time_dias_contratado=fornecedor.lead_time_dias_contratado,
        lead_time_dias_observado=lead_time_dias_observado,
        ativo=ativo,
    )


def make_estoque(
    sku: SKURaw,
    *,
    disponivel: int = 100,
    reservada: int = 0,
    atualizado_em: datetime | None = None,
) -> EstoqueRaw:
    return EstoqueRaw(
        sku_id=sku.id,
        quantidade_disponivel=disponivel,
        quantidade_reservada=reservada,
        atualizado_em=atualizado_em or datetime(2026, 9, 1, tzinfo=UTC),
    )


def make_venda(
    sku: SKURaw,
    data: datetime,
    quantidade: int,
    *,
    key: str | None = None,
    valor_unitario_reais: int = 3000,
    cliente_ref: str = "varejista-001",
) -> VendaRaw:
    ref = key or f"{sku.sku_code}|{data.isoformat()}|{quantidade}"
    return VendaRaw(
        id=uid("venda", ref),
        sku_id=sku.id,
        quantidade=quantidade,
        valor_unitario_reais=valor_unitario_reais,
        data=data,
        cliente_ref=cliente_ref,
    )


def make_movimentacao(
    sku: SKURaw,
    data: datetime,
    tipo: str,
    quantidade: int,
    *,
    key: str | None = None,
) -> MovimentacaoRaw:
    ref = key or f"{sku.sku_code}|{tipo}|{data.isoformat()}|{quantidade}"
    return MovimentacaoRaw(
        id=uid("mov", ref),
        sku_id=sku.id,
        tipo=tipo,
        quantidade=quantidade,
        data=data,
        referencia_tipo=None,
        referencia_id=None,
        observacao=None,
    )
