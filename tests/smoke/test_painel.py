"""Smoke do fluxo do comprador contra o Postgres real com o seed: a equipe de vendas
avisa, o SKU entra no painel de alertas, o comprador chefe registra a decisão de compra
e o SKU sai dos alertas para os decididos. O painel não chama o Jev.

O SKU do smoke é um que o cálculo não põe no painel, para o aviso ser o único motivo de
ele aparecer. No fim, a fixture apaga só o aviso e a decisão que o smoke criou.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from scripts.seed import (
    ATRASO_NAS_ENTREGAS_DA_KATRINA,
    DIAS_DE_ATRASO,
    KATRINA,
    QUEDA_SEM_ESTOQUE,
    RUPTURA_COM_PEDIDO_ATRASADO,
    RUPTURA_SEM_PEDIDO,
    TAPETE_MARROM,
)
from src.api.schemas import (
    AvisoResponse,
    CobrancaEntregaResponse,
    DecisaoCompraResponse,
    EntregaPendenteResponse,
    HistoricoDeAtrasosResponse,
    PainelDoRepositorResponse,
    PainelResponse,
    PrecosResponse,
    SKUResumoResponse,
)
from src.db.engine import get_engine
from src.usuarios.schemas import Usuario

pytestmark = pytest.mark.smoke


@pytest.fixture
def criados() -> Iterator[dict[str, list[UUID]]]:
    ids: dict[str, list[UUID]] = {"avisos": [], "decisoes_compra": [], "cobrancas_entrega": []}
    yield ids
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "DELETE FROM copilot.episodios_alerta e USING copilot.avisos a WHERE a.id = ANY(:ids) "
                "AND e.tipo = 'aviso' AND e.sku_code = a.sku_code AND e.aberto_em = a.criado_em"
            ),
            {"ids": ids["avisos"]},
        )
        for tabela, lista in ids.items():
            conn.execute(text(f"DELETE FROM copilot.{tabela} WHERE id = ANY(:ids)"), {"ids": lista})


def _painel(client: TestClient) -> PainelResponse:
    response = client.get("/painel")
    assert response.status_code == 200
    return PainelResponse.model_validate(response.json())


def test_aviso_painel_e_decisao_contra_o_seed(
    client: TestClient, criados: dict[str, list[UUID]], usuario_logado: Usuario
) -> None:
    antes = _painel(client)
    no_painel = {i.sku_code for i in antes.alertas} | {i.sku_code for i in antes.decididos}
    assert antes.alertas, "o seed deve ter SKUs pedindo atenção"
    assert antes.skus_com_erro == []
    with get_engine().connect() as conn:
        ativos = conn.execute(text("SELECT sku_code FROM erp.skus WHERE ativo ORDER BY sku_code")).scalars().all()
    sku_code = next(code for code in ativos if code not in no_painel)

    response = client.get(f"/skus/{sku_code}/analise")
    assert response.status_code == 200
    busca = client.get("/skus", params={"busca": response.json()["produto_nome"]})
    assert busca.status_code == 200
    assert sku_code in {SKUResumoResponse.model_validate(s).sku_code for s in busca.json()}

    response = client.post(
        "/avisos",
        json={"sku_code": sku_code, "tipo": "vendendo_muito", "comentario": "Smoke."},
    )
    assert response.status_code == 201
    aviso = AvisoResponse.model_validate(response.json())
    criados["avisos"].append(aviso.id)
    assert aviso.avisado_por == usuario_logado.nome

    item = next(i for i in _painel(client).alertas if i.sku_code == sku_code)
    assert item.so_por_aviso and item.motivos == []
    assert item.avisos_abertos == 1 and item.ultimo_aviso == aviso

    response = client.post(
        f"/skus/{sku_code}/decisoes",
        json={"tipo": "nao_comprar_agora", "motivo": "Smoke: estoque suficiente."},
    )
    assert response.status_code == 201
    decisao = DecisaoCompraResponse.model_validate(response.json())
    criados["decisoes_compra"].append(decisao.id)
    assert decisao.decidido_por == usuario_logado.nome
    assert decisao.politica_versao >= 1

    depois = _painel(client)
    assert sku_code not in {i.sku_code for i in depois.alertas}
    assert next(d for d in depois.decididos if d.sku_code == sku_code).decisao == decisao
    assert client.get(f"/skus/{sku_code}/avisos").json() == []
    assert client.get(f"/skus/{sku_code}/decisoes").json()[0]["id"] == str(decisao.id)


def test_cenarios_de_ruptura_do_seed_no_painel(client: TestClient) -> None:
    alertas = {i.sku_code: i for i in _painel(client).alertas}

    for sku_code in (RUPTURA_SEM_PEDIDO, RUPTURA_COM_PEDIDO_ATRASADO, QUEDA_SEM_ESTOQUE):
        assert "abaixo_do_piso_alerta" in alertas[sku_code].motivos
    assert alertas[QUEDA_SEM_ESTOQUE].disponivel == 0
    assert alertas[RUPTURA_SEM_PEDIDO].fornecedor_sugerido == "Katrina Têxtil"
    assert TAPETE_MARROM not in alertas


def test_queda_de_venda_do_seed_vai_para_o_repositor_ou_para_o_comprador(client: TestClient) -> None:
    response = client.get("/reposicao/painel")
    assert response.status_code == 200
    [tapete] = PainelDoRepositorResponse.model_validate(response.json()).quedas_de_venda

    assert tapete.sku_code == TAPETE_MARROM
    assert [d.quantidade for d in tapete.ultimos_dias] == [5, 0]
    assert 9 <= tapete.venda_diaria_base <= 11
    assert tapete.disponivel > 0
    parou = {i.sku_code for i in _painel(client).alertas if i.parou_de_vender}
    assert parou == {QUEDA_SEM_ESTOQUE}


def test_precos_contra_o_seed(client: TestClient) -> None:
    with get_engine().connect() as conn:
        sku_code = conn.execute(
            text(
                """
                SELECT s.sku_code FROM erp.pedidos_compra_itens i
                JOIN erp.pedidos_compra p ON p.id = i.pedido_id
                JOIN erp.skus s ON s.id = i.sku_id
                WHERE p.status <> 'cancelado' AND s.ativo
                ORDER BY s.sku_code LIMIT 1
                """
            )
        ).scalar_one()

    response = client.get(f"/skus/{sku_code}/precos")

    assert response.status_code == 200
    precos = PrecosResponse.model_validate(response.json())
    assert precos.historico and all(p.status != "cancelado" for p in precos.historico)
    assert precos.precos_atuais
    assert len(precos.substitutos) <= 10
    assert all(s.sku_code != sku_code for s in precos.substitutos)


def test_entrega_atrasada_do_seed_e_cobranca(
    client: TestClient, criados: dict[str, list[UUID]], usuario_logado: Usuario
) -> None:
    antes = _painel(client)
    katrina = antes.entregas_atrasadas[0]
    assert katrina.fornecedor_nome == KATRINA and katrina.tem_sku_em_ruptura
    [pedido] = katrina.pedidos
    assert pedido.dias_de_atraso == DIAS_DE_ATRASO
    assert RUPTURA_COM_PEDIDO_ATRASADO in {s.sku_code for s in pedido.skus}
    item = next(i for i in antes.alertas if i.sku_code == RUPTURA_COM_PEDIDO_ATRASADO)
    assert item.grupo == "entregas_atrasadas"

    nova_previsao = (datetime.now(UTC) + timedelta(days=3)).date()
    response = client.post(
        f"/pedidos/{pedido.pedido_id}/cobrancas",
        json={"nova_previsao": nova_previsao.isoformat(), "comentario": "Smoke."},
    )
    assert response.status_code == 201
    cobranca = CobrancaEntregaResponse.model_validate(response.json())
    criados["cobrancas_entrega"].append(cobranca.id)
    assert cobranca.cobrado_por == usuario_logado.nome

    depois = _painel(client)
    assert pedido.pedido_id not in {p.pedido_id for f in depois.entregas_atrasadas for p in f.pedidos}
    assert RUPTURA_COM_PEDIDO_ATRASADO not in {i.sku_code for i in depois.alertas if i.grupo == "entregas_atrasadas"}
    entregas = [
        EntregaPendenteResponse.model_validate(e)
        for e in client.get(f"/skus/{RUPTURA_COM_PEDIDO_ATRASADO}/entregas").json()
    ]
    cobrada = next(e for e in entregas if e.pedido_id == pedido.pedido_id)
    assert cobrada.atrasada and cobrada.cobranca_vigente and cobrada.cobrancas == [cobranca]

    historico = HistoricoDeAtrasosResponse.model_validate(
        client.get(f"/fornecedores/{katrina.fornecedor_id}/atrasos").json()
    )
    assert historico.entregas_recebidas == historico.entregas_atrasadas > 0
    assert historico.media_dias_de_atraso == ATRASO_NAS_ENTREGAS_DA_KATRINA
