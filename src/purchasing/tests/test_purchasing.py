"""Testes unitários do módulo `purchasing`."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.catalog.schemas import Fornecedor, FornecedorParaSKU
from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1, LeadTimeBase
from src.purchasing.schemas import LeadTimeOrigem, MotivoSemCompra, TipoAlerta
from src.purchasing.service import Purchasing
from src.sales.service import Sales
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
SKU = make_sku("TBC-BEG-70140")
KATRINA = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35)


def _vendas_100_por_mes() -> list:
    return [
        make_venda(SKU, datetime(2026, m, 5, tzinfo=UTC), 100, key=str(m))
        for m in range(3, 9)
    ]


def _katrina(**kwargs) -> FornecedorParaSKU:
    kwargs.setdefault("preco_unitario_reais", 1800)
    kwargs.setdefault("moq_unidades", 48)
    kwargs.setdefault("lead_time_dias_observado", 62)
    return make_fornecedor_sku(KATRINA, **kwargs)


def _purchasing(
    *,
    disponivel: int = 150,
    fornecedores: list[Fornecedor] | None = None,
    fornecedores_sku: list[FornecedorParaSKU] | None = None,
    politicas: InMemoryPoliticaCompraRepositorio | None = None,
    **kwargs,
) -> Purchasing:
    kwargs.setdefault("skus", [SKU])
    kwargs.setdefault("vendas", _vendas_100_por_mes())
    kwargs.setdefault("estoques", {SKU.sku_code: make_estoque(disponivel=disponivel)})
    adapter = InMemoryERPAdapter(
        fornecedores=[KATRINA] if fornecedores is None else fornecedores,
        fornecedores_por_sku={
            SKU.sku_code: [_katrina()] if fornecedores_sku is None else fornecedores_sku
        },
        **kwargs,
    )
    sales = Sales(adapter, now=NOW)
    inventory = Inventory(adapter, sales)
    return Purchasing(
        FichaSKU(Catalog(adapter), inventory, sales),
        inventory,
        sales,
        politicas or InMemoryPoliticaCompraRepositorio(),
        now=NOW,
    )


def test_exemplo_da_spec_numero_a_numero() -> None:
    # Giro 100/mês, lead time observado 62 dias, 150 disponíveis, nada em
    # trânsito, política v1.
    sugestao = _purchasing().sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.sku_code == SKU.sku_code
    assert sugestao.quantidade == 200
    assert sugestao.motivo is None
    assert sugestao.fornecedor is not None
    assert sugestao.fornecedor.fornecedor_nome == "Katrina Têxtil"
    assert sugestao.valor_estimado_centavos == 200 * 1800
    assert sugestao.politica_versao == 1

    calculo = sugestao.calculo
    assert calculo is not None
    assert calculo.giro_mensal == 100.0
    assert calculo.disponivel == 150
    assert calculo.em_transito == 0
    assert calculo.posicao == 150
    assert calculo.lead_time_dias == 62
    assert calculo.lead_time_origem == LeadTimeOrigem.OBSERVADO
    assert calculo.estoque_na_chegada == 0
    assert calculo.qtd_necessaria == 200
    assert calculo.cobertura_na_chegada_meses == pytest.approx(2.0)

    assert [a.tipo for a in sugestao.alertas] == [TipoAlerta.RUPTURA_ANTES_DA_CHEGADA]


def test_sku_inexistente_retorna_none() -> None:
    assert _purchasing().sugerir_pedido("NAO-EXISTE") is None


def test_sem_giro_sai_com_quantidade_zero_e_sem_calculo() -> None:
    sugestao = _purchasing(vendas=[]).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade == 0
    assert sugestao.motivo == MotivoSemCompra.SEM_GIRO
    assert sugestao.fornecedor is None
    assert sugestao.valor_estimado_centavos == 0
    assert sugestao.calculo is None
    assert sugestao.alertas == []
    assert sugestao.politica_versao == 1


def test_sem_fornecedor_sai_com_quantidade_zero_e_sem_calculo() -> None:
    sugestao = _purchasing(fornecedores_sku=[]).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade == 0
    assert sugestao.motivo == MotivoSemCompra.SEM_FORNECEDOR
    assert sugestao.fornecedor is None
    assert sugestao.calculo is None


def test_fornecedor_inativo_conta_como_sem_fornecedor() -> None:
    inativo = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35, ativo=False)
    sugestao = _purchasing(fornecedores=[inativo]).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.motivo == MotivoSemCompra.SEM_FORNECEDOR


def test_sem_giro_vem_antes_de_sem_fornecedor() -> None:
    sugestao = _purchasing(vendas=[], fornecedores_sku=[]).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.motivo == MotivoSemCompra.SEM_GIRO


def test_acima_do_ponto_de_reposicao_sai_com_calculo_e_sem_fornecedor() -> None:
    # Chegada com 1000 - 206,7 = 793,3 unidades, bem acima do piso de 100.
    sugestao = _purchasing(disponivel=1000).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade == 0
    assert sugestao.motivo == MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO
    assert sugestao.fornecedor is None
    assert sugestao.valor_estimado_centavos == 0
    assert sugestao.alertas == []
    assert sugestao.calculo is not None
    assert sugestao.calculo.estoque_na_chegada == pytest.approx(1000 - 100 * 62 / 30)
    assert sugestao.calculo.qtd_necessaria == 0


def _politica(**parametros) -> InMemoryPoliticaCompraRepositorio:
    repo = InMemoryPoliticaCompraRepositorio()
    repo.salvar_nova_versao(PARAMETROS_V1.model_copy(update=parametros))
    return repo


def test_em_transito_entra_na_posicao_e_reduz_a_quantidade() -> None:
    pedido = make_pedido_compra(KATRINA, "enviado")
    purchasing = _purchasing(
        pedidos_compra=[pedido],
        itens_pedido_compra=[make_item_pedido_compra(pedido, SKU, quantidade=100)],
    )

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.calculo is not None
    assert sugestao.calculo.em_transito == 100
    assert sugestao.calculo.posicao == 250
    # 250 - 206,7 = 43,3 na chegada; ceil(200 - 43,3) = 157.
    assert sugestao.calculo.estoque_na_chegada == pytest.approx(250 - 100 * 62 / 30)
    assert sugestao.quantidade == 157


def test_sem_ruptura_quando_a_posicao_cobre_o_lead_time() -> None:
    sugestao = _purchasing(disponivel=250).sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade > 0
    assert sugestao.alertas == []


def test_lead_time_contratado() -> None:
    purchasing = _purchasing(politicas=_politica(lead_time_base=LeadTimeBase.CONTRATADO))

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.calculo is not None
    assert sugestao.calculo.lead_time_dias == 35
    assert sugestao.calculo.lead_time_origem == LeadTimeOrigem.CONTRATADO
    # 150 - 116,7 = 33,3 na chegada; ceil(200 - 33,3) = 167.
    assert sugestao.quantidade == 167


def test_lead_time_observado_nulo_usa_o_contratado() -> None:
    purchasing = _purchasing(fornecedores_sku=[_katrina(lead_time_dias_observado=None)])

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.calculo is not None
    assert sugestao.calculo.lead_time_dias == 35
    assert sugestao.calculo.lead_time_origem == LeadTimeOrigem.CONTRATADO


@pytest.mark.parametrize(
    ("observado", "lead_time_dias", "origem"),
    [
        (62, 62, LeadTimeOrigem.OBSERVADO),
        (20, 35, LeadTimeOrigem.CONTRATADO),
        (None, 35, LeadTimeOrigem.CONTRATADO),
    ],
)
def test_lead_time_maior(
    observado: int | None, lead_time_dias: int, origem: LeadTimeOrigem
) -> None:
    purchasing = _purchasing(
        fornecedores_sku=[_katrina(lead_time_dias_observado=observado)],
        politicas=_politica(lead_time_base=LeadTimeBase.MAIOR),
    )

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.calculo is not None
    assert sugestao.calculo.lead_time_dias == lead_time_dias
    assert sugestao.calculo.lead_time_origem == origem


def test_moq_arredonda_a_quantidade_pra_cima() -> None:
    purchasing = _purchasing(fornecedores_sku=[_katrina(moq_unidades=300)])

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.calculo is not None
    assert sugestao.calculo.qtd_necessaria == 200
    assert sugestao.quantidade == 300
    assert sugestao.calculo.cobertura_na_chegada_meses == pytest.approx(3.0)
    assert sugestao.valor_estimado_centavos == 300 * 1800


def test_mudar_a_politica_muda_a_sugestao_e_a_versao() -> None:
    purchasing = _purchasing(politicas=_politica(ciclo_compra_meses=1.5))

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade == 250
    assert sugestao.politica_versao == 2


def test_quantidade_exata_nao_ganha_unidade_por_erro_de_ponto_flutuante() -> None:
    # 100 * (1 + 1.2) dá 220.00000000000003 em float.
    purchasing = _purchasing(politicas=_politica(ciclo_compra_meses=1.2))

    sugestao = purchasing.sugerir_pedido(SKU.sku_code)

    assert sugestao is not None
    assert sugestao.quantidade == 220
