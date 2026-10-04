"""Grava no schema `erp` do Postgres os mesmos dados de um `InMemoryERPAdapter`, para os
contratos rodarem a mesma suíte nas duas implementações. Os dados entram ao lado do seed e
saem no fim; quem usa escolhe códigos que não colidem com os do seed."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text

from src.db.engine import get_engine
from src.erp_adapter.in_memory import InMemoryERPAdapter


@contextmanager
def erp_no_banco(erp: InMemoryERPAdapter) -> Iterator[None]:
    produtos = {s.produto_id: s for s in erp.skus}
    codigos = {s.id: s.sku_code for s in erp.skus}
    with get_engine().begin() as conn:
        for sku in produtos.values():
            conn.execute(
                text("INSERT INTO erp.produtos (id, nome, categoria) VALUES (:id, :nome, :categoria)"),
                {"id": sku.produto_id, "nome": sku.produto_nome, "categoria": sku.categoria},
            )
        for sku in erp.skus:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.skus (id, produto_id, sku_code, cor, tamanho, gramatura, material, ativo)
                    VALUES (:id, :produto_id, :sku_code, :cor, :tamanho, :gramatura, :material, :ativo)
                    """
                ),
                sku.model_dump(include={"id", "produto_id", "sku_code", "cor", "tamanho", "gramatura", "material", "ativo"}),
            )
        for fornecedor in erp.fornecedores:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.fornecedores
                      (id, nome, cnpj, prazo_pagamento_padrao, pedido_minimo_reais, lead_time_dias_contratado, ativo)
                    VALUES (:id, :nome, :cnpj, :prazo_pagamento_padrao, :pedido_minimo_reais,
                            :lead_time_dias_contratado, :ativo)
                    """
                ),
                fornecedor.model_dump(),
            )
        sku_ids = {s.sku_code: s.id for s in erp.skus}
        for sku_code, vinculos in erp.vinculos.items():
            for vinculo in vinculos:
                conn.execute(
                    text(
                        """
                        INSERT INTO erp.fornecedores_skus
                          (fornecedor_id, sku_id, preco_unitario_atual, moq_unidades, lead_time_dias_observado)
                        VALUES (:fornecedor_id, :sku_id, :preco, :moq, :observado)
                        """
                    ),
                    {
                        "fornecedor_id": vinculo.fornecedor_id,
                        "sku_id": sku_ids[sku_code],
                        "preco": vinculo.preco_unitario_reais,
                        "moq": vinculo.moq_unidades,
                        "observado": vinculo.lead_time_dias_observado,
                    },
                )
        for sku_code, estoque in erp.estoques_por_sku.items():
            conn.execute(
                text(
                    """
                    INSERT INTO erp.estoque_snapshot (sku_id, quantidade_disponivel, quantidade_reservada, atualizado_em)
                    VALUES (:sku_id, :disponivel, :reservada, :atualizado_em)
                    """
                ),
                {
                    "sku_id": sku_ids[sku_code],
                    "disponivel": estoque.quantidade_disponivel,
                    "reservada": estoque.quantidade_reservada,
                    "atualizado_em": estoque.atualizado_em,
                },
            )
        if erp.vendas:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.vendas (id, sku_id, quantidade, valor_unitario_reais, data, cliente_ref)
                    VALUES (:id, :sku_id, :quantidade, :valor_unitario_reais, :data, :cliente_ref)
                    """
                ),
                [v.model_dump() for v in erp.vendas],
            )
        for pedido in erp.pedidos_compra:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra
                      (id, fornecedor_id, status, data_prevista_entrega, valor_total_reais, criado_em, recebido_em)
                    VALUES (:id, :fornecedor_id, :status, :data_prevista_entrega, 0, :criado_em, :recebido_em)
                    """
                ),
                pedido.model_dump(),
            )
        for item in erp.itens_pedido_compra:
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra_itens
                      (id, pedido_id, sku_id, quantidade, preco_unitario_reais, quantidade_recebida)
                    VALUES (gen_random_uuid(), :pedido_id, :sku_id, :quantidade, :preco, :recebida)
                    """
                ),
                {
                    "pedido_id": item.pedido_id,
                    "sku_id": item.sku_id,
                    "quantidade": item.quantidade,
                    "preco": item.preco_unitario_centavos,
                    "recebida": item.quantidade_recebida,
                },
            )
    try:
        yield
    finally:
        with get_engine().begin() as conn:
            ids_skus = list(codigos)
            pedidos = [p.id for p in erp.pedidos_compra]
            conn.execute(text("DELETE FROM erp.pedidos_compra_itens WHERE pedido_id = ANY(:ids)"), {"ids": pedidos})
            conn.execute(text("DELETE FROM erp.pedidos_compra WHERE id = ANY(:ids)"), {"ids": pedidos})
            conn.execute(text("DELETE FROM erp.vendas WHERE sku_id = ANY(:ids)"), {"ids": ids_skus})
            conn.execute(text("DELETE FROM erp.skus WHERE id = ANY(:ids)"), {"ids": ids_skus})
            conn.execute(
                text("DELETE FROM erp.fornecedores WHERE id = ANY(:ids)"),
                {"ids": [f.id for f in erp.fornecedores]},
            )
            conn.execute(text("DELETE FROM erp.produtos WHERE id = ANY(:ids)"), {"ids": list(produtos)})
