"""O retrato em lote e a leitura de um SKU dão a mesma sugestão de pedido para os mesmos
dados, no adapter em memória e no Postgres. No Postgres os dados entram ao lado do seed
(códigos `RET-`) e só eles são comparados."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.catalog.service import Catalog
from src.db.engine import get_engine
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.erp_adapter.port import ERPAdapter
from src.erp_adapter.postgres import PostgresERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1, LeadTimeBase
from src.purchasing.schemas import MotivoSemCompra
from src.purchasing.service import Purchasing
from src.sales.service import Sales
from tests.erp_no_banco import erp_no_banco
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM erp.skus LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(not _db_disponivel(), reason="Postgres com schema erp precisa estar disponível")

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
PRODUTO = "Toalha Contrato Retrato"


def _sku(cor: str):
    return make_sku(f"RET-{cor[:4].upper()}-01", produto_nome=PRODUTO, cor=cor)


COMPRANDO = _sku("azul")
COM_TRANSITO = _sku("verde")
SOBRANDO = _sku("bege")
NOVO = _sku("lilas")
SEM_GIRO = _sku("cinza")
SEM_FORNECEDOR = _sku("rosa")
VOLTOU_A_VENDER = _sku("preto")
SEM_ESTOQUE = _sku("marrom")
TODOS = [COMPRANDO, COM_TRANSITO, SOBRANDO, NOVO, SEM_GIRO, SEM_FORNECEDOR, VOLTOU_A_VENDER, SEM_ESTOQUE]
COM_ESTOQUE = [s for s in TODOS if s != SEM_ESTOQUE]

KATRINA = make_fornecedor("Retrato Katrina Têxtil", lead_time_dias_contratado=35)
BRAVO = make_fornecedor("Retrato Bravo Malhas", lead_time_dias_contratado=20)


def _mensal(sku, quantidade: int, meses: range) -> list:
    return [make_venda(sku, datetime(2026, m, 5, tzinfo=UTC), quantidade, key=f"{sku.sku_code}|{m}") for m in meses]


def _montar() -> InMemoryERPAdapter:
    a_caminho = make_pedido_compra(BRAVO, "enviado", key="retrato-enviado")
    return InMemoryERPAdapter(
        skus=TODOS,
        fornecedores=[KATRINA, BRAVO],
        fornecedores_por_sku={
            s.sku_code: [
                make_fornecedor_sku(KATRINA, preco_unitario_reais=1800, moq_unidades=48, lead_time_dias_observado=62),
                make_fornecedor_sku(BRAVO, preco_unitario_reais=2000, moq_unidades=24, lead_time_dias_observado=20),
            ]
            for s in TODOS
            if s != SEM_FORNECEDOR
        },
        estoques={
            COMPRANDO.sku_code: make_estoque(disponivel=40),
            COM_TRANSITO.sku_code: make_estoque(disponivel=40),
            SOBRANDO.sku_code: make_estoque(disponivel=900),
            NOVO.sku_code: make_estoque(disponivel=10),
            SEM_GIRO.sku_code: make_estoque(disponivel=10),
            SEM_FORNECEDOR.sku_code: make_estoque(disponivel=10),
            VOLTOU_A_VENDER.sku_code: make_estoque(disponivel=5),
        },
        vendas=[
            *_mensal(COMPRANDO, 100, range(3, 10)),
            *_mensal(COM_TRANSITO, 100, range(3, 9)),
            *_mensal(SOBRANDO, 100, range(3, 9)),
            make_venda(NOVO, NOW - timedelta(days=20), 30),
            make_venda(SEM_GIRO, datetime(2024, 1, 10, tzinfo=UTC), 3),
            *_mensal(SEM_FORNECEDOR, 50, range(3, 9)),
            make_venda(VOLTOU_A_VENDER, datetime(2025, 6, 10, tzinfo=UTC), 40),
            *_mensal(VOLTOU_A_VENDER, 30, range(7, 9)),
            *_mensal(SEM_ESTOQUE, 100, range(3, 9)),
        ],
        pedidos_compra=[a_caminho],
        itens_pedido_compra=[make_item_pedido_compra(a_caminho, COM_TRANSITO, quantidade=100, quantidade_recebida=50)],
    )


@pytest.fixture
def postgres() -> Iterator[PostgresERPAdapter]:
    with erp_no_banco(_montar()):
        yield PostgresERPAdapter(get_engine())


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def erp(request: pytest.FixtureRequest) -> ERPAdapter:
    if request.param == "memoria":
        return _montar()
    return request.getfixturevalue("postgres")


def _servicos(erp: ERPAdapter, lead_time_base: LeadTimeBase) -> tuple[FichaSKU, Purchasing]:
    catalog = Catalog(erp)
    sales = Sales(erp, now=NOW)
    ficha_sku = FichaSKU(catalog, Inventory(erp, sales), sales)
    politicas = InMemoryPoliticaCompraRepositorio(v1=PARAMETROS_V1.model_copy(update={"lead_time_base": lead_time_base}))
    return ficha_sku, Purchasing(catalog, ficha_sku, politicas, erp, now=NOW)


@pytest.mark.parametrize("lead_time_base", [LeadTimeBase.IGNORAR, LeadTimeBase.OBSERVADO])
def test_retrato_e_leitura_por_sku_dao_a_mesma_sugestao(erp: ERPAdapter, lead_time_base: LeadTimeBase) -> None:
    ficha_sku, purchasing = _servicos(erp, lead_time_base)

    sugestoes = purchasing.sugerir_pedidos(ficha_sku.retrato())

    for sku in COM_ESTOQUE:
        assert sugestoes[sku.sku_code] == purchasing.sugerir_pedido(sku.sku_code), sku.sku_code
    assert SEM_ESTOQUE.sku_code not in sugestoes


def test_retrato_cobre_cada_caminho_da_sugestao(erp: ERPAdapter) -> None:
    ficha_sku, purchasing = _servicos(erp, LeadTimeBase.IGNORAR)
    retrato = ficha_sku.retrato()

    sugestoes = purchasing.sugerir_pedidos(retrato)

    assert {sku.sku_code: sugestoes[sku.sku_code].motivo for sku in COM_ESTOQUE} == {
        COMPRANDO.sku_code: None,
        COM_TRANSITO.sku_code: None,
        SOBRANDO.sku_code: MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO,
        NOVO.sku_code: MotivoSemCompra.SKU_NOVO,
        SEM_GIRO.sku_code: MotivoSemCompra.SEM_GIRO,
        SEM_FORNECEDOR.sku_code: MotivoSemCompra.SEM_FORNECEDOR,
        VOLTOU_A_VENDER.sku_code: None,
    }
    # Giro 100 (a venda de setembro é do mês corrente e fica fora) e 40 disponíveis, abaixo do
    # piso de reposição de 100: compra 100 * (1 + 2) - 40. Com 50 a caminho, a posição é 90.
    assert sugestoes[COMPRANDO.sku_code].quantidade == 260
    assert sugestoes[COM_TRANSITO.sku_code].quantidade == 210
    # Vendeu em junho de 2025 e voltou em julho: o histórico passa de 6 meses, então o giro
    # divide por 6 (60 / 6 = 10), não por 2.
    assert retrato.fichas[VOLTOU_A_VENDER.sku_code].giro.unidades_por_mes == pytest.approx(10.0)
    assert retrato.fichas[NOVO.sku_code].primeira_venda == NOW - timedelta(days=20)
    assert SEM_ESTOQUE.sku_code not in retrato.fichas
    assert SEM_ESTOQUE.sku_code in {s.sku_code for s in retrato.skus}
