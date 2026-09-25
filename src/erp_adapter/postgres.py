"""Implementação Postgres do `ERPAdapter`.

Todas as queries vão pelo schema `erp`. Junta nome e categoria do
produto no `SKU` para evitar N+1 nos consumidores.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.inventory.schemas import Estoque, Movimentacao
from src.sales.schemas import Venda


_SKU_SELECT = """
    SELECT
        s.id, s.produto_id, s.sku_code, s.cor, s.tamanho, s.gramatura,
        s.material, s.ativo, p.nome AS produto_nome, p.categoria AS produto_categoria
    FROM erp.skus s
    JOIN erp.produtos p ON p.id = s.produto_id
"""


def _row_to_sku(row: Row) -> SKU:
    return SKU(
        id=row.id,
        produto_id=row.produto_id,
        sku_code=row.sku_code,
        produto_nome=row.produto_nome,
        categoria=row.produto_categoria,
        cor=row.cor,
        tamanho=row.tamanho,
        gramatura=row.gramatura,
        material=row.material,
        ativo=row.ativo,
    )


class PostgresERPAdapter(ERPAdapter):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def carregar_sku(self, sku_code: str) -> SKU | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SKU_SELECT + " WHERE s.sku_code = :sku_code"),
                {"sku_code": sku_code},
            ).one_or_none()
        return _row_to_sku(row) if row is not None else None

    def listar_skus(self) -> list[SKU]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(_SKU_SELECT + " WHERE s.ativo = TRUE ORDER BY s.sku_code")
            ).all()
        return [_row_to_sku(r) for r in rows]

    def carregar_fornecedor(self, fornecedor_id: UUID) -> Fornecedor | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, nome, cnpj, prazo_pagamento_padrao,
                           pedido_minimo_reais, lead_time_dias_contratado, ativo
                    FROM erp.fornecedores
                    WHERE id = :fornecedor_id
                    """
                ),
                {"fornecedor_id": fornecedor_id},
            ).one_or_none()
        if row is None:
            return None
        return Fornecedor(
            id=row.id,
            nome=row.nome,
            cnpj=row.cnpj,
            prazo_pagamento_padrao=row.prazo_pagamento_padrao,
            pedido_minimo_reais=row.pedido_minimo_reais,
            lead_time_dias_contratado=row.lead_time_dias_contratado,
            ativo=row.ativo,
        )

    def fornecedores_de(self, sku_code: str) -> list[FornecedorParaSKU]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT fs.fornecedor_id, f.nome AS fornecedor_nome,
                           fs.preco_unitario_atual, fs.moq_unidades,
                           f.lead_time_dias_contratado, fs.lead_time_dias_observado,
                           f.prazo_pagamento_padrao, f.pedido_minimo_reais
                    FROM erp.fornecedores_skus fs
                    JOIN erp.fornecedores f ON f.id = fs.fornecedor_id
                    JOIN erp.skus s ON s.id = fs.sku_id
                    WHERE s.sku_code = :sku_code AND fs.ativo = TRUE AND f.ativo = TRUE
                    ORDER BY fs.preco_unitario_atual
                    """
                ),
                {"sku_code": sku_code},
            ).all()
        return [
            FornecedorParaSKU(
                fornecedor_id=r.fornecedor_id,
                fornecedor_nome=r.fornecedor_nome,
                preco_unitario_reais=r.preco_unitario_atual,
                moq_unidades=r.moq_unidades,
                lead_time_dias_contratado=r.lead_time_dias_contratado,
                lead_time_dias_observado=r.lead_time_dias_observado,
                prazo_pagamento_padrao=r.prazo_pagamento_padrao,
                pedido_minimo_reais=r.pedido_minimo_reais,
            )
            for r in rows
        ]

    def estoque_de(self, sku_code: str) -> Estoque | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT e.quantidade_disponivel, e.quantidade_reservada,
                           e.atualizado_em
                    FROM erp.estoque_snapshot e
                    JOIN erp.skus s ON s.id = e.sku_id
                    WHERE s.sku_code = :sku_code
                    """
                ),
                {"sku_code": sku_code},
            ).one_or_none()
        if row is None:
            return None
        return Estoque(
            quantidade_disponivel=row.quantidade_disponivel,
            quantidade_reservada=row.quantidade_reservada,
            atualizado_em=row.atualizado_em,
        )

    def vendas_de(self, sku_code: str, desde: datetime) -> list[Venda]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT v.id, v.sku_id, v.quantidade, v.valor_unitario_reais,
                           v.data, v.cliente_ref
                    FROM erp.vendas v
                    JOIN erp.skus s ON s.id = v.sku_id
                    WHERE s.sku_code = :sku_code AND v.data >= :desde
                    ORDER BY v.data
                    """
                ),
                {"sku_code": sku_code, "desde": desde},
            ).all()
        return [
            Venda(
                id=r.id,
                sku_id=r.sku_id,
                quantidade=r.quantidade,
                valor_unitario_reais=r.valor_unitario_reais,
                data=r.data,
                cliente_ref=r.cliente_ref,
            )
            for r in rows
        ]

    def movimentacoes_de(
        self, sku_code: str, desde: datetime
    ) -> list[Movimentacao]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT m.id, m.sku_id, m.tipo::text AS tipo, m.quantidade,
                           m.data, m.referencia_tipo, m.referencia_id, m.observacao
                    FROM erp.movimentacoes_estoque m
                    JOIN erp.skus s ON s.id = m.sku_id
                    WHERE s.sku_code = :sku_code AND m.data >= :desde
                    ORDER BY m.data
                    """
                ),
                {"sku_code": sku_code, "desde": desde},
            ).all()
        return [
            Movimentacao(
                id=r.id,
                sku_id=r.sku_id,
                tipo=r.tipo,
                quantidade=r.quantidade,
                data=r.data,
                referencia_tipo=r.referencia_tipo,
                referencia_id=r.referencia_id,
                observacao=r.observacao,
            )
            for r in rows
        ]
