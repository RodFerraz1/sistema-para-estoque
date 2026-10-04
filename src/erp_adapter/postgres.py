"""Implementação Postgres do `ERPAdapter`.

Todas as queries vão pelo schema `erp`. Junta nome e categoria do
produto no `SKU` para evitar N+1 nos consumidores.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row

from src.catalog.schemas import SKU, Fornecedor, FornecedorParaSKU
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.schemas import ItemDePedido
from src.inventory.schemas import (
    STATUS_EM_TRANSITO,
    EntregaRecebida,
    Estoque,
    ItemEmTransito,
    Movimentacao,
)
from src.sales.schemas import Venda, VendasDoDia, VendasDoMes


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


_FORNECEDORES_SELECT = """
    SELECT s.sku_code, fs.fornecedor_id, f.nome AS fornecedor_nome,
           fs.preco_unitario_atual, fs.moq_unidades,
           f.lead_time_dias_contratado, fs.lead_time_dias_observado,
           f.prazo_pagamento_padrao, f.pedido_minimo_reais
    FROM erp.fornecedores_skus fs
    JOIN erp.fornecedores f ON f.id = fs.fornecedor_id
    JOIN erp.skus s ON s.id = fs.sku_id
    WHERE fs.ativo = TRUE AND f.ativo = TRUE
"""


def _row_to_fornecedor(r: Row) -> FornecedorParaSKU:
    return FornecedorParaSKU(
        fornecedor_id=r.fornecedor_id,
        fornecedor_nome=r.fornecedor_nome,
        preco_unitario_reais=r.preco_unitario_atual,
        moq_unidades=r.moq_unidades,
        lead_time_dias_contratado=r.lead_time_dias_contratado,
        lead_time_dias_observado=r.lead_time_dias_observado,
        prazo_pagamento_padrao=r.prazo_pagamento_padrao,
        pedido_minimo_reais=r.pedido_minimo_reais,
    )


_EM_TRANSITO_SELECT = """
    SELECT s.sku_code, p.id AS pedido_id, p.fornecedor_id, f.nome AS fornecedor_nome,
           p.status::text AS status,
           i.quantidade - i.quantidade_recebida AS quantidade_pendente,
           p.data_prevista_entrega
    FROM erp.pedidos_compra_itens i
    JOIN erp.pedidos_compra p ON p.id = i.pedido_id
    JOIN erp.fornecedores f ON f.id = p.fornecedor_id
    JOIN erp.skus s ON s.id = i.sku_id
    WHERE p.status::text = ANY(:status)
      AND i.quantidade > i.quantidade_recebida
"""


def _row_to_em_transito(r: Row) -> ItemEmTransito:
    return ItemEmTransito(
        pedido_id=r.pedido_id,
        fornecedor_id=r.fornecedor_id,
        fornecedor_nome=r.fornecedor_nome,
        status=r.status,
        quantidade_pendente=r.quantidade_pendente,
        data_prevista_entrega=r.data_prevista_entrega,
    )


def _estoque(r: Row) -> Estoque:
    return Estoque(
        quantidade_disponivel=r.quantidade_disponivel,
        quantidade_reservada=r.quantidade_reservada,
        atualizado_em=r.atualizado_em,
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
                text(_FORNECEDORES_SELECT + " AND s.sku_code = :sku_code ORDER BY fs.preco_unitario_atual"),
                {"sku_code": sku_code},
            ).all()
        return [_row_to_fornecedor(r) for r in rows]

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
        return _estoque(row) if row is not None else None

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
                    _EM_TRANSITO_SELECT
                    + " AND s.sku_code = :sku_code ORDER BY p.data_prevista_entrega NULLS LAST, p.id"
                ),
                {"sku_code": sku_code, "status": list(STATUS_EM_TRANSITO)},
            ).all()
        return [_row_to_em_transito(r) for r in rows]

    def itens_de_pedido_de(self, sku_code: str) -> list[ItemDePedido]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT p.id AS pedido_id, p.criado_em, p.fornecedor_id,
                           f.nome AS fornecedor_nome, p.status::text AS status,
                           i.quantidade, i.preco_unitario_reais
                    FROM erp.pedidos_compra_itens i
                    JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                    JOIN erp.fornecedores f ON f.id = p.fornecedor_id
                    JOIN erp.skus s ON s.id = i.sku_id
                    WHERE s.sku_code = :sku_code
                    ORDER BY p.criado_em DESC, p.id::text DESC
                    """
                ),
                {"sku_code": sku_code},
            ).all()
        # `preco_unitario_reais` guarda centavos, apesar do nome.
        return [
            ItemDePedido(
                pedido_id=r.pedido_id,
                criado_em=r.criado_em,
                fornecedor_id=r.fornecedor_id,
                fornecedor_nome=r.fornecedor_nome,
                status=r.status,
                quantidade=r.quantidade,
                preco_unitario_centavos=r.preco_unitario_reais,
            )
            for r in rows
        ]

    def entregas_recebidas_de(self, fornecedor_id: UUID) -> list[EntregaRecebida]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id AS pedido_id, data_prevista_entrega, recebido_em
                    FROM erp.pedidos_compra
                    WHERE fornecedor_id = :fornecedor_id AND status = 'recebido_total'
                      AND data_prevista_entrega IS NOT NULL AND recebido_em IS NOT NULL
                    ORDER BY recebido_em DESC, id::text DESC
                    """
                ),
                {"fornecedor_id": fornecedor_id},
            ).all()
        return [EntregaRecebida.model_validate(r._asdict()) for r in rows]

    def estoques(self) -> dict[str, Estoque]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT s.sku_code, e.quantidade_disponivel, e.quantidade_reservada,
                           e.atualizado_em
                    FROM erp.estoque_snapshot e
                    JOIN erp.skus s ON s.id = e.sku_id
                    WHERE s.ativo = TRUE
                    """
                )
            ).all()
        return {r.sku_code: _estoque(r) for r in rows}

    def giros(self, desde: datetime) -> dict[str, list[VendasDoMes]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT s.sku_code, m.mes, m.quantidade, m.primeira_venda
                    FROM (
                        SELECT v.sku_id, date_trunc('month', v.data AT TIME ZONE 'UTC') AS mes,
                               sum(v.quantidade) AS quantidade, min(v.data) AS primeira_venda
                        FROM erp.vendas v
                        WHERE v.data >= :desde
                        GROUP BY v.sku_id, mes
                    ) m
                    JOIN erp.skus s ON s.id = m.sku_id
                    WHERE s.ativo = TRUE
                    ORDER BY m.sku_id, m.mes
                    """
                ),
                {"desde": desde},
            ).all()
        por_sku: dict[str, list[VendasDoMes]] = defaultdict(list)
        for sku_code, mes, quantidade, primeira_venda in rows:
            por_sku[sku_code].append(VendasDoMes(mes.year, mes.month, quantidade, primeira_venda))
        return dict(por_sku)

    def vendas_diarias(self, desde: datetime) -> dict[str, list[VendasDoDia]]:
        # Uma linha por SKU, com os dias como deslocamento inteiro desde `inicio`: trazer uma
        # linha por SKU e dia, com o código e a data em cada uma, custava o dobro com 5.000 SKUs.
        inicio = desde.astimezone(UTC).date()
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT s.sku_code, d.dias, d.quantidades
                    FROM (
                        SELECT sku_id, array_agg(dia - :inicio ORDER BY dia) AS dias,
                               array_agg(quantidade ORDER BY dia) AS quantidades
                        FROM (
                            SELECT v.sku_id, (v.data AT TIME ZONE 'UTC')::date AS dia,
                                   sum(v.quantidade)::int AS quantidade
                            FROM erp.vendas v
                            WHERE v.data >= :desde
                            GROUP BY v.sku_id, dia
                        ) por_dia
                        GROUP BY sku_id
                    ) d
                    JOIN erp.skus s ON s.id = d.sku_id
                    WHERE s.ativo = TRUE
                    """
                ),
                {"desde": desde, "inicio": inicio},
            ).all()
        datas: dict[int, date] = {}
        return {
            sku_code: [
                VendasDoDia(datas.get(n) or datas.setdefault(n, inicio + timedelta(days=n)), quantidade)
                for n, quantidade in zip(dias, quantidades)
            ]
            for sku_code, dias, quantidades in rows
        }

    def fornecedores_por_sku(self) -> dict[str, list[FornecedorParaSKU]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(_FORNECEDORES_SELECT + " AND s.ativo = TRUE ORDER BY s.sku_code, fs.preco_unitario_atual")
            ).all()
        por_sku: dict[str, list[FornecedorParaSKU]] = defaultdict(list)
        for r in rows:
            por_sku[r.sku_code].append(_row_to_fornecedor(r))
        return dict(por_sku)

    def itens_em_transito(self) -> dict[str, list[ItemEmTransito]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    _EM_TRANSITO_SELECT
                    + " AND s.ativo = TRUE ORDER BY s.sku_code, p.data_prevista_entrega NULLS LAST, p.id"
                ),
                {"status": list(STATUS_EM_TRANSITO)},
            ).all()
        por_sku: dict[str, list[ItemEmTransito]] = defaultdict(list)
        for r in rows:
            por_sku[r.sku_code].append(_row_to_em_transito(r))
        return dict(por_sku)
