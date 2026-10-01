"""Testes HTTP de `/sugestoes` com ERP, política, busca, Jev e fila em memória.

Giro de 100 por mês nos seis meses fechados antes do atual e fornecedor Boa Vista com
lead time de 30 dias, R$ 20,00 a unidade e MOQ 48. `URGENTE` acaba antes da compra
chegar (destaque), `REGULAR` chega com meio mês de estoque e `SOBRANDO` não compra.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.ai.dependencies import get_decision_model, get_embedder, get_trechos_repositorio
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel
from src.aprovacao.dependencies import get_sugestoes_fila_repositorio
from src.aprovacao.in_memory import InMemorySugestoesFilaRepositorio
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1, MotivoDestaque
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_pedido_compra,
    make_sku,
    make_trecho,
    make_venda,
    repositorio_com,
)

BOA_VISTA = make_fornecedor("Boa Vista Têxtil", lead_time_dias_contratado=30)
URGENTE = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto")
REGULAR = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto")
SOBRANDO = make_sku("TBC-AZUL-70140-01", produto_nome="Toalha Banho Conforto")
ATRASO = "reunioes/revisao.md#boa-vista"
DEPENDENCIAS = (
    get_erp_adapter,
    get_politica_compra_repositorio,
    get_embedder,
    get_trechos_repositorio,
    get_decision_model,
    get_sugestoes_fila_repositorio,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def _meses_fechados(quantos: int) -> list[datetime]:
    hoje = datetime.now(UTC)
    ano, mes = hoje.year, hoje.month
    datas = []
    for _ in range(quantos):
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        datas.append(datetime(ano, mes, 5, tzinfo=UTC))
    return datas


def preparar(
    decisao: InMemoryDecisionModel | None = None,
    *,
    com_pedido_anterior: bool = True,
    motivos_de_destaque: tuple[MotivoDestaque, ...] | None = None,
) -> InMemoryERPAdapter:
    disponiveis = {URGENTE: 50, REGULAR: 150, SOBRANDO: 900}
    erp = InMemoryERPAdapter(
        skus=list(disponiveis),
        fornecedores=[BOA_VISTA],
        fornecedores_por_sku={
            sku.sku_code: [make_fornecedor_sku(BOA_VISTA, preco_unitario_reais=2000, lead_time_dias_observado=30)]
            for sku in disponiveis
        },
        estoques={sku.sku_code: make_estoque(disponivel=d) for sku, d in disponiveis.items()},
        vendas=[
            make_venda(sku, data, 100, key=f"{sku.sku_code}-{data:%Y-%m}")
            for sku in disponiveis
            for data in _meses_fechados(6)
        ],
        pedidos_compra=[make_pedido_compra(BOA_VISTA, "recebido_total")] if com_pedido_anterior else [],
    )
    embedder = FakeEmbedder()
    trechos = repositorio_com([make_trecho(ATRASO, "Boa Vista atrasou as entregas")], embedder)
    politicas = InMemoryPoliticaCompraRepositorio()
    if motivos_de_destaque is not None:
        politicas.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"motivos_de_destaque": motivos_de_destaque}))
    fila = InMemorySugestoesFilaRepositorio()
    decisao = decisao or InMemoryDecisionModel(padrao={"relevante": 0.9, "tem_evidencia": 0.9})
    app.dependency_overrides[get_erp_adapter] = lambda: erp
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: politicas
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_trechos_repositorio] = lambda: trechos
    app.dependency_overrides[get_decision_model] = lambda: decisao
    app.dependency_overrides[get_sugestoes_fila_repositorio] = lambda: fila
    return erp


def pendentes(client: TestClient) -> list[dict]:
    response = client.get("/sugestoes")
    assert response.status_code == 200
    return response.json()


def id_de(client: TestClient, sku_code: str) -> str:
    return next(s["id"] for s in pendentes(client) if s["sku_code"] == sku_code)


def test_gerar_devolve_o_resultado_e_a_fila_fica_em_ordem(client: TestClient) -> None:
    preparar()

    response = client.post("/sugestoes/gerar")

    assert response.status_code == 200
    assert response.json() == {
        "geradas": 2,
        "substituidas": 0,
        "skus_avaliados": 3,
        "sinais_indisponiveis": False,
    }
    fila = pendentes(client)
    assert [(s["sku_code"], s["destaque"]) for s in fila] == [
        (URGENTE.sku_code, True),
        (REGULAR.sku_code, False),
    ]
    regular = fila[1]
    assert regular["status"] == "pendente"
    assert regular["produto_nome"] == "Toalha Banho Conforto"
    assert regular["cobertura_na_chegada_sem_compra_meses"] == pytest.approx(0.5)
    assert regular["sugestao"]["sugestao"]["quantidade"] == 150
    assert regular["sugestao"]["sugestao"]["fornecedor"]["fornecedor_nome"] == "Boa Vista Têxtil"
    assert regular["sugestao"]["sinais"] == []
    assert regular["faixa"] == {
        "faixa": 1,
        "aprovadores": "comprador chefe",
        "exige_justificativa": False,
        "ajustes": [],
    }
    assert regular["decidido_em"] is None
    assert regular["pedido_compra_id"] is None


@pytest.mark.parametrize(
    ("motivos_de_destaque", "destaque"),
    [(None, False), ((MotivoDestaque.ATRASO_DO_FORNECEDOR,), True)],
    ids=["politica-padrao", "atraso-na-politica"],
)
def test_gerar_com_sinal_do_corpus_mostra_o_sinal_e_destaca_se_a_politica_manda(
    client: TestClient, motivos_de_destaque: tuple[MotivoDestaque, ...] | None, destaque: bool
) -> None:
    preparar(
        InMemoryDecisionModel(
            padrao={"relevante": 0.9, "tem_evidencia": 0.9}, sinais={ATRASO: {"atraso_do_fornecedor": 0.97}}
        ),
        motivos_de_destaque=motivos_de_destaque,
    )

    client.post("/sugestoes/gerar")

    regular = next(s for s in pendentes(client) if s["sku_code"] == REGULAR.sku_code)
    assert regular["destaque"] is destaque
    assert regular["sugestao"]["sinais"] == [
        {
            "tipo": "atraso_do_fornecedor",
            "mensagem": "Os documentos relatam atraso de entrega da Boa Vista Têxtil.",
            "trechos": [ATRASO],
            "probabilidade": 0.97,
        }
    ]


def test_gerar_com_o_jev_fora_do_ar_responde_200_sem_sinais(client: TestClient) -> None:
    preparar(InMemoryDecisionModel(falhar_trechos=True, falhar_sinais=True))

    response = client.post("/sugestoes/gerar")

    assert response.status_code == 200
    assert response.json()["sinais_indisponiveis"] is True
    assert response.json()["geradas"] == 2
    assert all(s["sugestao"]["sinais"] is None for s in pendentes(client))


def test_gerar_de_novo_conta_as_substituidas(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")

    response = client.post("/sugestoes/gerar")

    assert response.json()["substituidas"] == 2
    assert len(client.get("/sugestoes", params={"status": "substituida"}).json()) == 2


def test_listar_com_status_invalido_da_422(client: TestClient) -> None:
    preparar()

    assert client.get("/sugestoes", params={"status": "qualquer"}).status_code == 422


def test_carregar_por_id(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)

    response = client.get(f"/sugestoes/{id}")

    assert response.status_code == 200
    assert response.json()["sku_code"] == REGULAR.sku_code


def test_carregar_inexistente_da_404(client: TestClient) -> None:
    preparar()

    response = client.get(f"/sugestoes/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]


def test_faixa_da_quantidade_editada(client: TestClient) -> None:
    erp = preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)

    response = client.get(f"/sugestoes/{id}/faixa", params={"quantidade": 400})

    assert response.status_code == 200
    assert response.json() == {
        "faixa": 2,
        "aprovadores": "comprador chefe + gerente comercial ou sócio financeiro",
        "exige_justificativa": True,
        "ajustes": ["Viola o teto da política de estoque: sobe da faixa 1 para a 2."],
    }
    assert erp.itens_pedido_compra == []
    assert client.get(f"/sugestoes/{id}").json()["status"] == "pendente"


@pytest.mark.parametrize("params", [{"quantidade": 10}, {}], ids=["abaixo-do-moq", "sem-quantidade"])
def test_faixa_com_quantidade_invalida_da_422(client: TestClient, params: dict) -> None:
    preparar()
    client.post("/sugestoes/gerar")

    response = client.get(f"/sugestoes/{id_de(client, REGULAR.sku_code)}/faixa", params=params)

    assert response.status_code == 422


def test_faixa_de_sugestao_inexistente_da_404(client: TestClient) -> None:
    preparar()

    assert client.get(f"/sugestoes/{uuid4()}/faixa", params={"quantidade": 100}).status_code == 404


def test_aprovar_cria_o_pedido_e_tira_da_fila(client: TestClient) -> None:
    erp = preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)

    response = client.post(f"/sugestoes/{id}/aprovar", json={"aprovado_por": "Ana"})

    assert response.status_code == 200
    aprovada = response.json()
    assert aprovada["status"] == "aprovada"
    assert aprovada["decidido_por"] == "Ana"
    assert aprovada["quantidade_aprovada"] == 150
    [pedido] = [p for p in erp.pedidos_compra if p.status == "aprovado"]
    assert aprovada["pedido_compra_id"] == str(pedido.id)
    assert id not in {s["id"] for s in pendentes(client)}
    assert [s["id"] for s in client.get("/sugestoes", params={"status": "aprovada"}).json()] == [id]


def test_aprovar_com_quantidade_editada(client: TestClient) -> None:
    erp = preparar()
    client.post("/sugestoes/gerar")

    response = client.post(
        f"/sugestoes/{id_de(client, REGULAR.sku_code)}/aprovar",
        json={"aprovado_por": "Ana", "quantidade": 400, "justificativa": "Compra de oportunidade."},
    )

    assert response.status_code == 200
    assert response.json()["quantidade_aprovada"] == 400
    assert response.json()["faixa"]["faixa"] == 2
    assert response.json()["justificativa"] == "Compra de oportunidade."
    assert [i.quantidade for i in erp.itens_pedido_compra] == [400]


def test_aprovar_abaixo_do_moq_da_422(client: TestClient) -> None:
    erp = preparar()
    client.post("/sugestoes/gerar")

    response = client.post(
        f"/sugestoes/{id_de(client, REGULAR.sku_code)}/aprovar", json={"aprovado_por": "Ana", "quantidade": 10}
    )

    assert response.status_code == 422
    assert "MOQ" in response.json()["detail"]
    assert erp.itens_pedido_compra == []


def test_aprovar_sem_a_justificativa_que_a_faixa_exige_da_422(client: TestClient) -> None:
    erp = preparar(com_pedido_anterior=False)
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)

    response = client.post(f"/sugestoes/{id}/aprovar", json={"aprovado_por": "Ana"})

    assert response.status_code == 422
    assert "justificativa" in response.json()["detail"]
    assert erp.pedidos_compra == []
    assert client.get(f"/sugestoes/{id}").json()["status"] == "pendente"


def test_aprovar_sem_nome_da_422(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")

    response = client.post(f"/sugestoes/{id_de(client, REGULAR.sku_code)}/aprovar", json={"aprovado_por": "  "})

    assert response.status_code == 422


def test_aprovar_ja_decidida_da_409(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)
    client.post(f"/sugestoes/{id}/aprovar", json={"aprovado_por": "Ana"})

    response = client.post(f"/sugestoes/{id}/aprovar", json={"aprovado_por": "Ana"})

    assert response.status_code == 409
    assert "aprovada" in response.json()["detail"]


def test_aprovar_inexistente_da_404(client: TestClient) -> None:
    preparar()

    response = client.post(f"/sugestoes/{uuid4()}/aprovar", json={"aprovado_por": "Ana"})

    assert response.status_code == 404


def test_rejeitar_registra_o_motivo(client: TestClient) -> None:
    erp = preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)

    response = client.post(f"/sugestoes/{id}/rejeitar", json={"rejeitado_por": "Ana", "motivo": "Caro demais."})

    assert response.status_code == 200
    rejeitada = response.json()
    assert rejeitada["status"] == "rejeitada"
    assert rejeitada["decidido_por"] == "Ana"
    assert rejeitada["motivo_rejeicao"] == "Caro demais."
    assert rejeitada["pedido_compra_id"] is None
    assert erp.itens_pedido_compra == []
    assert [s["id"] for s in client.get("/sugestoes", params={"status": "rejeitada"}).json()] == [id]


def test_rejeitar_sem_motivo_da_422(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")

    response = client.post(
        f"/sugestoes/{id_de(client, REGULAR.sku_code)}/rejeitar", json={"rejeitado_por": "Ana", "motivo": " "}
    )

    assert response.status_code == 422


def test_rejeitar_ja_decidida_da_409(client: TestClient) -> None:
    preparar()
    client.post("/sugestoes/gerar")
    id = id_de(client, REGULAR.sku_code)
    client.post(f"/sugestoes/{id}/rejeitar", json={"rejeitado_por": "Ana", "motivo": "Caro demais."})

    response = client.post(f"/sugestoes/{id}/rejeitar", json={"rejeitado_por": "Ana", "motivo": "De novo."})

    assert response.status_code == 409


def test_rejeitar_inexistente_da_404(client: TestClient) -> None:
    preparar()

    response = client.post(f"/sugestoes/{uuid4()}/rejeitar", json={"rejeitado_por": "Ana", "motivo": "Motivo."})

    assert response.status_code == 404
