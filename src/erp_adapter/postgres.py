"""Implementação Postgres do `ERPAdapter`.

Todas as queries vão pelo schema `erp`. Junta `produto_nome` e
`produto_categoria` no `SKURaw` para evitar N+1 nos consumidores.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import (
    EstoqueRaw,
    FiltrosSKU,
    FornecedorRaw,
    FornecedorSKURaw,
    MovimentacaoRaw,
    SKURaw,
    VendaRaw,
)


_SKU_SELECT = """
    SELECT
        s.id, s.produto_id, s.sku_code, s.cor, s.tamanho, s.gramatura,
        s.material, s.ativo, p.nome AS produto_nome, p.categoria AS produto_categoria
    FROM erp.skus s
    JOIN erp.produtos p ON p.id = s.produto_id
"""


def _row_to_sku(row: Row) -> SKURaw:
    return SKURaw(
        id=row.id,
        produto_id=row.produto_id,
        sku_code=row.sku_code,
        cor=row.cor,
        tamanho=row.tamanho,
        gramatura=row.gramatura,
        material=row.material,
        ativo=row.ativo,
        produto_nome=row.produto_nome,
        produto_categoria=row.produto_categoria,
    )


class PostgresERPAdapter(ERPAdapter):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_sku_raw(self, sku_id: UUID) -> SKURaw | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SKU_SELECT + " WHERE s.id = :sku_id"),
                {"sku_id": sku_id},
            ).one_or_none()
        return _row_to_sku(row) if row is not None else None

    def get_sku_raw_por_codigo(self, sku_code: str) -> SKURaw | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(_SKU_SELECT + " WHERE s.sku_code = :sku_code"),
                {"sku_code": sku_code},
            ).one_or_none()
        return _row_to_sku(row) if row is not None else None

    def list_skus_raw(self, filtros: FiltrosSKU) -> list[SKURaw]:
        clauses: list[str] = []
        params: dict[str, object] = {}
        if filtros.categoria is not None:
            clauses.append("p.categoria = :categoria")
            params["categoria"] = filtros.categoria
        if filtros.ativo is not None:
            clauses.append("s.ativo = :ativo")
            params["ativo"] = filtros.ativo
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(_SKU_SELECT + where + " ORDER BY s.sku_code"), params
            ).all()
        return [_row_to_sku(r) for r in rows]

    def get_fornecedor_raw(self, fornecedor_id: UUID) -> FornecedorRaw | None:
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
        return FornecedorRaw(
            id=row.id,
            nome=row.nome,
            cnpj=row.cnpj,
            prazo_pagamento_padrao=row.prazo_pagamento_padrao,
            pedido_minimo_reais=row.pedido_minimo_reais,
            lead_time_dias_contratado=row.lead_time_dias_contratado,
            ativo=row.ativo,
        )

    def list_fornecedores_para_sku(self, sku_id: UUID) -> list[FornecedorSKURaw]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT fs.fornecedor_id, fs.sku_id, f.nome AS fornecedor_nome,
                           fs.preco_unitario_atual, fs.moq_unidades,
                           f.lead_time_dias_contratado, fs.lead_time_dias_observado,
                           f.prazo_pagamento_padrao, f.pedido_minimo_reais,
                           fs.ativo
                    FROM erp.fornecedores_skus fs
                    JOIN erp.fornecedores f ON f.id = fs.fornecedor_id
                    WHERE fs.sku_id = :sku_id AND fs.ativo = TRUE AND f.ativo = TRUE
                    ORDER BY fs.preco_unitario_atual
                    """
                ),
                {"sku_id": sku_id},
            ).all()
        return [
            FornecedorSKURaw(
                fornecedor_id=r.fornecedor_id,
                sku_id=r.sku_id,
                fornecedor_nome=r.fornecedor_nome,
                preco_unitario_atual=r.preco_unitario_atual,
                moq_unidades=r.moq_unidades,
                lead_time_dias_contratado=r.lead_time_dias_contratado,
                lead_time_dias_observado=r.lead_time_dias_observado,
                prazo_pagamento_padrao=r.prazo_pagamento_padrao,
                pedido_minimo_reais=r.pedido_minimo_reais,
                ativo=r.ativo,
            )
            for r in rows
        ]

    def get_estoque_atual(self, sku_id: UUID) -> EstoqueRaw | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT sku_id, quantidade_disponivel, quantidade_reservada,
                           atualizado_em
                    FROM erp.estoque_snapshot
                    WHERE sku_id = :sku_id
                    """
                ),
                {"sku_id": sku_id},
            ).one_or_none()
        if row is None:
            return None
        return EstoqueRaw(
            sku_id=row.sku_id,
            quantidade_disponivel=row.quantidade_disponivel,
            quantidade_reservada=row.quantidade_reservada,
            atualizado_em=row.atualizado_em,
        )

    def list_movimentacoes(
        self, sku_id: UUID, desde: datetime
    ) -> list[MovimentacaoRaw]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, sku_id, tipo::text AS tipo, quantidade, data,
                           referencia_tipo, referencia_id, observacao
                    FROM erp.movimentacoes_estoque
                    WHERE sku_id = :sku_id AND data >= :desde
                    ORDER BY data
                    """
                ),
                {"sku_id": sku_id, "desde": desde},
            ).all()
        return [
            MovimentacaoRaw(
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

    def list_vendas(self, sku_id: UUID, desde: datetime) -> list[VendaRaw]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, sku_id, quantidade, valor_unitario_reais, data,
                           cliente_ref
                    FROM erp.vendas
                    WHERE sku_id = :sku_id AND data >= :desde
                    ORDER BY data
                    """
                ),
                {"sku_id": sku_id, "desde": desde},
            ).all()
        return [
            VendaRaw(
                id=r.id,
                sku_id=r.sku_id,
                quantidade=r.quantidade,
                valor_unitario_reais=r.valor_unitario_reais,
                data=r.data,
                cliente_ref=r.cliente_ref,
            )
            for r in rows
        ]
