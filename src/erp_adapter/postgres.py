"""Implementação Postgres do `ERPAdapter`.

Todas as queries vão pelo schema `erp`. Junta nome e categoria do
produto no `SKU` para evitar N+1 nos consumidores.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import ItemNovoPedido
from src.inventory.schemas import (
    STATUS_EM_TRANSITO,
    Estoque,
    ItemEmTransito,
    Movimentacao,
)
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

    def itens_em_transito_de(self, sku_code: str) -> list[ItemEmTransito]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT p.id AS pedido_id, p.fornecedor_id,
                           p.status::text AS status,
                           i.quantidade - i.quantidade_recebida AS quantidade_pendente,
                           p.data_prevista_entrega
                    FROM erp.pedidos_compra_itens i
                    JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                    JOIN erp.skus s ON s.id = i.sku_id
                    WHERE s.sku_code = :sku_code
                      AND p.status::text = ANY(:status)
                      AND i.quantidade > i.quantidade_recebida
                    ORDER BY p.data_prevista_entrega NULLS LAST, p.id
                    """
                ),
                {"sku_code": sku_code, "status": list(STATUS_EM_TRANSITO)},
            ).all()
        return [
            ItemEmTransito(
                pedido_id=r.pedido_id,
                fornecedor_id=r.fornecedor_id,
                status=r.status,
                quantidade_pendente=r.quantidade_pendente,
                data_prevista_entrega=r.data_prevista_entrega,
            )
            for r in rows
        ]

    def fornecedor_tem_pedido(self, fornecedor_id: UUID) -> bool:
        with self._engine.connect() as conn:
            return conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM erp.pedidos_compra
                        WHERE fornecedor_id = :fornecedor_id
                          AND status NOT IN ('rascunho', 'cancelado')
                    )
                    """
                ),
                {"fornecedor_id": fornecedor_id},
            ).scalar_one()

    def criar_pedido_compra(
        self,
        fornecedor_id: UUID,
        itens: list[ItemNovoPedido],
        data_prevista_entrega: date,
        observacao: str,
    ) -> UUID:
        if not itens:
            raise ValueError("pedido de compra sem itens")
        pedido_id = uuid4()
        with self._engine.begin() as conn:
            fornecedor_existe = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM erp.fornecedores WHERE id = :id)"),
                {"id": fornecedor_id},
            ).scalar_one()
            if not fornecedor_existe:
                raise ValueError(f"fornecedor {fornecedor_id} não existe")
            sku_ids = dict(
                conn.execute(
                    text("SELECT sku_code, id FROM erp.skus WHERE sku_code = ANY(:codes)"),
                    {"codes": [i.sku_code for i in itens]},
                ).all()
            )
            if faltando := sorted({i.sku_code for i in itens} - sku_ids.keys()):
                raise ValueError(f"SKU inexistente: {', '.join(faltando)}")

            # `valor_total_reais` e `preco_unitario_reais` guardam centavos, apesar do nome.
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra
                      (id, fornecedor_id, status, aprovado_em, data_prevista_entrega,
                       valor_total_reais, observacao)
                    VALUES (:id, :fornecedor_id, 'aprovado', now(), :data_prevista_entrega,
                            :valor_total, :observacao)
                    """
                ),
                {
                    "id": pedido_id,
                    "fornecedor_id": fornecedor_id,
                    "data_prevista_entrega": data_prevista_entrega,
                    "valor_total": sum(i.quantidade * i.preco_unitario_centavos for i in itens),
                    "observacao": observacao,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO erp.pedidos_compra_itens
                      (id, pedido_id, sku_id, quantidade, preco_unitario_reais)
                    VALUES (:id, :pedido_id, :sku_id, :quantidade, :preco_unitario)
                    """
                ),
                [
                    {
                        "id": uuid4(),
                        "pedido_id": pedido_id,
                        "sku_id": sku_ids[i.sku_code],
                        "quantidade": i.quantidade,
                        "preco_unitario": i.preco_unitario_centavos,
                    }
                    for i in itens
                ],
            )
        return pedido_id
