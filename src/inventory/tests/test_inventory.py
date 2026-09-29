"""Testes unitários do módulo `inventory`."""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.erp_adapter.in_memory import InMemoryERPAdapter, StatusPedidoCompra
from src.inventory.service import Inventory
from src.sales.service import Sales
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def _inv(**kwargs) -> Inventory:
    adapter = InMemoryERPAdapter(**kwargs)
    return Inventory(adapter, Sales(adapter, now=NOW))


def test_estoque_atual_retorna_dto() -> None:
    sku = make_sku("A")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=200, reservada=15)},
    )

    estoque = inv.estoque_atual(sku.sku_code)

    assert estoque is not None
    assert estoque.quantidade_disponivel == 200
    assert estoque.quantidade_reservada == 15


def test_estoque_atual_inexistente_retorna_none() -> None:
    inv = _inv()

    assert inv.estoque_atual("FANTASMA") is None


def test_cobertura_calcula_meses() -> None:
    sku = make_sku("A")
    # 6 vendas de 60 unidades em meses fechados diferentes -> giro 60/mês.
    vendas = [
        make_venda(sku, datetime(2026, 3, 10, tzinfo=UTC), 60, key="1"),
        make_venda(sku, datetime(2026, 4, 10, tzinfo=UTC), 60, key="2"),
        make_venda(sku, datetime(2026, 5, 10, tzinfo=UTC), 60, key="3"),
        make_venda(sku, datetime(2026, 6, 10, tzinfo=UTC), 60, key="4"),
        make_venda(sku, datetime(2026, 7, 10, tzinfo=UTC), 60, key="5"),
        make_venda(sku, datetime(2026, 8, 10, tzinfo=UTC), 60, key="6"),
    ]
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=120, reservada=0)},
        vendas=vendas,
    )

    cobertura = inv.cobertura_meses(sku.sku_code)

    assert cobertura.sem_giro is False
    assert cobertura.meses == 2.0


def test_cobertura_sem_giro_quando_giro_zero() -> None:
    """SKU com estoque mas sem vendas: sem_giro=True, meses=None."""
    sku = make_sku("A")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=50)},
        vendas=[],
    )

    cobertura = inv.cobertura_meses(sku.sku_code)

    assert cobertura.sem_giro is True
    assert cobertura.meses is None


def test_cobertura_sem_giro_quando_sku_inexistente() -> None:
    inv = _inv()

    cobertura = inv.cobertura_meses("FANTASMA")

    assert cobertura.sem_giro is True
    assert cobertura.meses is None


def test_cobertura_zero_quando_estoque_zero_e_ha_giro() -> None:
    sku = make_sku("A")
    vendas = [
        make_venda(sku, datetime(2026, m, 10, tzinfo=UTC), 60, key=str(m))
        for m in range(3, 9)
    ]
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=0)},
        vendas=vendas,
    )

    cobertura = inv.cobertura_meses(sku.sku_code)

    assert cobertura.sem_giro is False
    assert cobertura.meses == 0.0


def _vendas_giro_60(sku, key_prefix: str = "") -> list:
    return [
        make_venda(sku, datetime(2026, m, 10, tzinfo=UTC), 60,
                   key=f"{key_prefix}{m}")
        for m in range(3, 9)
    ]


def test_abaixo_do_piso_retorna_apenas_skus_em_alerta() -> None:
    baixo = make_sku("BAIXO", produto_nome="Toalha Baixa")
    alto = make_sku("ALTO", produto_nome="Toalha Alta")
    inv = _inv(
        skus=[baixo, alto],
        estoques={
            baixo.sku_code: make_estoque(disponivel=20),
            alto.sku_code: make_estoque(disponivel=500),
        },
        vendas=_vendas_giro_60(baixo, "b") + _vendas_giro_60(alto, "a"),
    )

    resultado = inv.abaixo_do_piso(dias_piso=20)

    assert len(resultado) == 1
    assert resultado[0].sku_code == "BAIXO"
    assert resultado[0].produto_nome == "Toalha Baixa"
    assert resultado[0].cobertura_meses == 20 / 60


def test_abaixo_do_piso_ordena_por_cobertura_crescente() -> None:
    urgente = make_sku("URG")
    menos = make_sku("MENOS")
    inv = _inv(
        skus=[menos, urgente],
        estoques={
            urgente.sku_code: make_estoque(disponivel=5),
            menos.sku_code: make_estoque(disponivel=25),
        },
        vendas=_vendas_giro_60(urgente, "u") + _vendas_giro_60(menos, "m"),
    )

    resultado = inv.abaixo_do_piso(dias_piso=20)

    assert [r.sku_code for r in resultado] == ["URG", "MENOS"]


def test_abaixo_do_piso_ignora_sku_sem_giro() -> None:
    sku = make_sku("SEM-VENDAS")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=0)},
        vendas=[],
    )

    assert inv.abaixo_do_piso(dias_piso=20) == []


def test_abaixo_do_piso_ignora_sku_inativo() -> None:
    ativo = make_sku("ATIVO")
    inativo = make_sku("INATIVO", ativo=False)
    inv = _inv(
        skus=[ativo, inativo],
        estoques={
            ativo.sku_code: make_estoque(disponivel=10),
            inativo.sku_code: make_estoque(disponivel=1),
        },
        vendas=_vendas_giro_60(ativo, "a") + _vendas_giro_60(inativo, "i"),
    )

    resultado = inv.abaixo_do_piso(dias_piso=20)

    assert [r.sku_code for r in resultado] == ["ATIVO"]


def test_abaixo_do_piso_lista_vazia_quando_ninguem_abaixo() -> None:
    sku = make_sku("A")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=1000)},
        vendas=_vendas_giro_60(sku),
    )

    assert inv.abaixo_do_piso(dias_piso=20) == []


def test_abaixo_do_piso_parametro_dias_muda_limite() -> None:
    """Cobertura de ~0.83 meses (25/30): abaixo de 30d (1.0), acima de 20d (0.667)."""
    sku = make_sku("A")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=25)},
        vendas=_vendas_giro_60(sku),
    )

    # cobertura = 25/60 = 0.417 meses. Piso 20d = 0.667 -> abaixo.
    # Piso 10d = 0.333 -> acima.
    assert len(inv.abaixo_do_piso(dias_piso=20)) == 1
    assert inv.abaixo_do_piso(dias_piso=10) == []


def test_em_transito_conta_pendente_de_pedido_enviado() -> None:
    sku = make_sku("A")
    fornecedor = make_fornecedor()
    pedido = make_pedido_compra(
        fornecedor, "enviado", data_prevista_entrega=date(2026, 10, 20)
    )
    inv = _inv(
        skus=[sku],
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, sku, quantidade=120)],
    )

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 120
    [item] = em_transito.itens
    assert item.pedido_id == pedido.id
    assert item.fornecedor_id == fornecedor.id
    assert item.status == "enviado"
    assert item.quantidade_pendente == 120
    assert item.data_prevista_entrega == date(2026, 10, 20)


@pytest.mark.parametrize("status", ["aprovado", "enviado", "recebido_parcial"])
def test_em_transito_conta_status_de_pedido_aberto(status: StatusPedidoCompra) -> None:
    sku = make_sku("A")
    pedido = make_pedido_compra(make_fornecedor(), status)
    inv = _inv(
        skus=[sku],
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, sku, quantidade=50)],
    )

    assert inv.em_transito(sku.sku_code).total_unidades == 50


@pytest.mark.parametrize("status", ["rascunho", "cancelado", "recebido_total"])
def test_em_transito_ignora_status_fora_do_transito(
    status: StatusPedidoCompra,
) -> None:
    sku = make_sku("A")
    pedido = make_pedido_compra(make_fornecedor(), status)
    inv = _inv(
        skus=[sku],
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, sku, quantidade=50)],
    )

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 0
    assert em_transito.itens == []


def test_em_transito_recebido_parcial_conta_so_o_pendente() -> None:
    sku = make_sku("A")
    pedido = make_pedido_compra(make_fornecedor(), "recebido_parcial")
    inv = _inv(
        skus=[sku],
        pedidos_compra=[pedido],
        itens_pedido_compra=[
            make_item_pedido_compra(pedido, sku, quantidade=100, quantidade_recebida=40)
        ],
    )

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 60
    assert [i.quantidade_pendente for i in em_transito.itens] == [60]


def test_em_transito_ignora_item_ja_recebido_por_inteiro() -> None:
    sku = make_sku("A")
    pedido = make_pedido_compra(make_fornecedor(), "recebido_parcial")
    inv = _inv(
        skus=[sku],
        pedidos_compra=[pedido],
        itens_pedido_compra=[
            make_item_pedido_compra(pedido, sku, quantidade=100, quantidade_recebida=100)
        ],
    )

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 0
    assert em_transito.itens == []


def test_em_transito_soma_pedidos_e_ignora_outros_skus() -> None:
    sku = make_sku("A")
    outro = make_sku("B")
    katrina = make_fornecedor("Katrina Têxtil")
    buddemeyer = make_fornecedor("Buddemeyer")
    tardio = make_pedido_compra(
        katrina, "enviado", data_prevista_entrega=date(2026, 11, 1)
    )
    cedo = make_pedido_compra(
        buddemeyer, "aprovado", data_prevista_entrega=date(2026, 10, 1)
    )
    inv = _inv(
        skus=[sku, outro],
        pedidos_compra=[tardio, cedo],
        itens_pedido_compra=[
            make_item_pedido_compra(tardio, sku, quantidade=30),
            make_item_pedido_compra(tardio, outro, quantidade=999),
            make_item_pedido_compra(cedo, sku, quantidade=70),
        ],
    )

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 100
    assert [i.pedido_id for i in em_transito.itens] == [cedo.id, tardio.id]


def test_em_transito_sku_sem_pedidos_devolve_zero() -> None:
    sku = make_sku("A")
    inv = _inv(skus=[sku])

    em_transito = inv.em_transito(sku.sku_code)

    assert em_transito.total_unidades == 0
    assert em_transito.itens == []


def test_cobertura_ignora_em_transito() -> None:
    sku = make_sku("A")
    pedido = make_pedido_compra(make_fornecedor(), "enviado")
    inv = _inv(
        skus=[sku],
        estoques={sku.sku_code: make_estoque(disponivel=120)},
        vendas=_vendas_giro_60(sku),
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, sku, quantidade=600)],
    )

    assert inv.cobertura_meses(sku.sku_code).meses == 2.0
