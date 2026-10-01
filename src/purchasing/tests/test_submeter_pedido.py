"""`Purchasing.faixa_aprovacao` e `Purchasing.submeter_pedido` com o ERP em memória.

Cenário do exemplo da spec de sugestão: giro de 100 por mês, 150 disponíveis,
Katrina a R$ 18,00 com MOQ 48 e lead time observado de 62 dias. A sugestão é
de 200 unidades (R$ 3.600,00).
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1
from src.purchasing.schemas import MotivoSemCompra, SugestaoPedido, TipoAlerta
from src.purchasing.service import Purchasing, QuantidadeInvalida, SugestaoSemCompra
from src.sales.service import Sales
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_pedido_compra,
    make_sku,
    make_venda,
)


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
SKU = make_sku("TBC-BEG-70140")
KATRINA = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35)


def _montar(
    *,
    moq: int = 48,
    com_pedido_anterior: bool = True,
    politicas: InMemoryPoliticaCompraRepositorio | None = None,
) -> tuple[Purchasing, InMemoryERPAdapter]:
    erp = InMemoryERPAdapter(
        skus=[SKU],
        fornecedores=[KATRINA],
        fornecedores_por_sku={
            SKU.sku_code: [
                make_fornecedor_sku(
                    KATRINA, preco_unitario_reais=1800, moq_unidades=moq, lead_time_dias_observado=62
                )
            ]
        },
        estoques={SKU.sku_code: make_estoque(disponivel=150)},
        vendas=[make_venda(SKU, datetime(2026, m, 5, tzinfo=UTC), 100, key=str(m)) for m in range(3, 9)],
        pedidos_compra=[make_pedido_compra(KATRINA, "recebido_total")] if com_pedido_anterior else [],
    )
    sales = Sales(erp, now=NOW)
    inventory = Inventory(erp, sales)
    purchasing = Purchasing(
        FichaSKU(Catalog(erp), inventory, sales),
        inventory,
        sales,
        politicas or InMemoryPoliticaCompraRepositorio(),
        erp,
        now=NOW,
    )
    return purchasing, erp


def _sugestao(purchasing: Purchasing) -> SugestaoPedido:
    sugestao = purchasing.sugerir_pedido(SKU.sku_code)
    assert sugestao is not None
    return sugestao


def _politica_com_faixas(faixa_1: int, faixa_2: int, faixa_3: int) -> InMemoryPoliticaCompraRepositorio:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)
    repo.salvar_nova_versao(
        PARAMETROS_V1.model_copy(
            update={"faixa_1_ate_reais": faixa_1, "faixa_2_ate_reais": faixa_2, "faixa_3_ate_reais": faixa_3}
        )
    )
    return repo


def test_faixa_da_sugestao_de_reposicao_regular() -> None:
    purchasing, _ = _montar()
    sugestao = _sugestao(purchasing)
    assert sugestao.quantidade == 200

    faixa = purchasing.faixa_aprovacao(sugestao)

    assert faixa.faixa == 1
    assert faixa.aprovadores == "comprador chefe"
    assert faixa.exige_justificativa is False


def test_fornecedor_sem_pedido_anterior_vai_para_a_faixa_3() -> None:
    purchasing, _ = _montar(com_pedido_anterior=False)

    faixa = purchasing.faixa_aprovacao(_sugestao(purchasing))

    assert faixa.faixa == 3
    assert faixa.exige_justificativa is True


def test_quantidade_editada_recalcula_o_valor() -> None:
    purchasing, _ = _montar(politicas=_politica_com_faixas(3_000, 5_000, 100_000))
    sugestao = _sugestao(purchasing)

    # 200 x R$ 18,00 = R$ 3.600,00 (faixa 2, desce para 1); 290 x R$ 18,00 = R$ 5.220,00
    # (faixa 3, desce para 2). A cobertura na chegada fica em 2,9 meses, dentro do teto.
    assert purchasing.faixa_aprovacao(sugestao).faixa == 1
    assert purchasing.faixa_aprovacao(sugestao, quantidade=290).faixa == 2


def test_quantidade_editada_acima_do_teto_sobe_a_faixa() -> None:
    purchasing, _ = _montar()
    sugestao = _sugestao(purchasing)

    # 1.000 unidades chegam com 10 meses de cobertura, acima do teto de 3.
    faixa = purchasing.faixa_aprovacao(sugestao, quantidade=1_000)

    assert faixa.faixa == 3
    assert faixa.ajustes == ["Viola o teto da política de estoque: sobe da faixa 2 para a 3."]


def test_sugestao_com_alerta_de_teto_sobe_a_faixa() -> None:
    purchasing, _ = _montar(moq=400)
    sugestao = _sugestao(purchasing)
    assert TipoAlerta.VIOLA_TETO in {a.tipo for a in sugestao.alertas}

    faixa = purchasing.faixa_aprovacao(sugestao)

    assert faixa.faixa == 2


def test_faixa_usa_a_versao_da_politica_da_sugestao_e_nao_a_ativa() -> None:
    politicas = InMemoryPoliticaCompraRepositorio(now=NOW)
    purchasing, _ = _montar(politicas=politicas)
    sugestao = _sugestao(purchasing)
    politicas.salvar_nova_versao(
        PARAMETROS_V1.model_copy(
            update={"faixa_1_ate_reais": 1_000, "faixa_2_ate_reais": 2_000, "faixa_3_ate_reais": 3_000}
        )
    )

    # Com a v2, R$ 3.600,00 seria faixa 4 e desceria para a 3.
    assert sugestao.politica_versao == 1
    assert purchasing.faixa_aprovacao(sugestao).faixa == 1


def test_faixa_de_sugestao_com_versao_de_politica_inexistente_falha() -> None:
    purchasing, _ = _montar()
    sugestao = _sugestao(purchasing).model_copy(update={"politica_versao": 99})

    with pytest.raises(LookupError, match="99"):
        purchasing.faixa_aprovacao(sugestao)


def test_faixa_com_quantidade_abaixo_do_moq_e_rejeitada() -> None:
    purchasing, _ = _montar()

    with pytest.raises(QuantidadeInvalida):
        purchasing.faixa_aprovacao(_sugestao(purchasing), quantidade=47)


def test_submeter_cria_pedido_aprovado_no_erp() -> None:
    purchasing, erp = _montar()
    sugestao = _sugestao(purchasing)

    pedido_id = purchasing.submeter_pedido(sugestao, 200, "Comprador Chefe", "fila-123")

    [pedido] = [p for p in erp.pedidos_compra if p.id == pedido_id]
    assert pedido.fornecedor_id == KATRINA.id
    assert pedido.status == "aprovado"
    assert pedido.data_prevista_entrega == date(2026, 11, 16)
    assert pedido.valor_total_centavos == 200 * 1800
    assert pedido.observacao == (
        "Criado pelo Copilot a partir da sugestão fila-123, aprovado por Comprador Chefe."
    )
    [item] = [i for i in erp.itens_pedido_compra if i.pedido_id == pedido_id]
    assert (item.sku_id, item.quantidade, item.preco_unitario_centavos) == (SKU.id, 200, 1800)


def test_submeter_usa_a_quantidade_aprovada() -> None:
    purchasing, erp = _montar()

    pedido_id = purchasing.submeter_pedido(_sugestao(purchasing), 250, "Comprador Chefe", "fila-123")

    [item] = [i for i in erp.itens_pedido_compra if i.pedido_id == pedido_id]
    assert item.quantidade == 250


@pytest.mark.parametrize("quantidade", [0, -10, 47])
def test_submeter_rejeita_quantidade_zero_ou_abaixo_do_moq(quantidade: int) -> None:
    purchasing, erp = _montar()
    antes = list(erp.pedidos_compra)

    with pytest.raises(QuantidadeInvalida):
        purchasing.submeter_pedido(_sugestao(purchasing), quantidade, "Comprador Chefe", "fila-123")

    assert erp.pedidos_compra == antes


def test_submeter_aceita_quantidade_igual_ao_moq() -> None:
    purchasing, erp = _montar()

    purchasing.submeter_pedido(_sugestao(purchasing), 48, "Comprador Chefe", "fila-123")

    assert len(erp.itens_pedido_compra) == 1


def test_sugestao_sem_compra_nao_vira_pedido() -> None:
    purchasing, erp = _montar()
    sugestao = _sugestao(purchasing).model_copy(
        update={
            "quantidade": 0,
            "motivo": MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO,
            "fornecedor": None,
        }
    )

    with pytest.raises(SugestaoSemCompra):
        purchasing.submeter_pedido(sugestao, 200, "Comprador Chefe", "fila-123")
    with pytest.raises(SugestaoSemCompra):
        purchasing.faixa_aprovacao(sugestao)

    assert erp.itens_pedido_compra == []


def test_pedido_submetido_entra_em_transito_na_proxima_sugestao() -> None:
    purchasing, _ = _montar()

    purchasing.submeter_pedido(_sugestao(purchasing), 200, "Comprador Chefe", "fila-123")

    proxima = _sugestao(purchasing)
    assert proxima.calculo is not None
    assert proxima.calculo.em_transito == 200
    assert proxima.quantidade == 0
    assert proxima.motivo == MotivoSemCompra.ACIMA_DO_PONTO_DE_REPOSICAO


def test_primeiro_pedido_submetido_tira_o_fornecedor_da_faixa_3() -> None:
    purchasing, _ = _montar(com_pedido_anterior=False)
    sugestao = _sugestao(purchasing)
    assert purchasing.faixa_aprovacao(sugestao).faixa == 3

    purchasing.submeter_pedido(sugestao, 200, "Comprador Chefe", "fila-123")

    assert purchasing.faixa_aprovacao(sugestao).faixa == 1
