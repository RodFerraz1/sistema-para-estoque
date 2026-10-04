"""Testes HTTP de `POST /chat` e `GET /chat/registros` com ERP, política, busca,
Jev, redator e registros em memória."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.ai.dependencies import (
    get_decision_model,
    get_embedder,
    get_redator,
    get_registros_decisao,
    get_trechos_repositorio,
)
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel, InMemoryRegistrosDecisao
from src.ai.schemas import Entendimento, Intencao
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.usuarios.schemas import Usuario
from tests.fakes import (
    RedatorGravador,
    make_entendimento,
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_relacao,
    make_sku,
    make_venda,
    make_trecho,
    repositorio_com,
)

SKU = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege")
DA_TELA = make_sku("LC-BRAN-CASAL-01", produto_nome="Lençol Casal", cor="branco", tamanho="casal")
PERGUNTA = "Qual a situação do SKU TBC-BEGE-70140-01?"
DEPENDENCIAS = (
    get_erp_adapter,
    get_politica_compra_repositorio,
    get_embedder,
    get_trechos_repositorio,
    get_decision_model,
    get_redator,
    get_registros_decisao,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def preparar(
    decisao: InMemoryDecisionModel | None = None, redator: RedatorGravador | None = None
) -> InMemoryRegistrosDecisao:
    """Sem `decisao`, o Jev fica o de verdade, que falha sem `JEV_KEY`. O redator
    e os registros são sempre trocados, para nenhum teste chamar o LLM nem gravar
    no banco."""
    embedder = FakeEmbedder()
    trechos = repositorio_com(
        [
            make_trecho("contratos/katrina.md#prazos", "lead time da Katrina"),
            make_trecho("reunioes/q1.md#katrina", "lead time da Katrina em dias"),
        ],
        embedder,
    )
    katrina = make_fornecedor("Katrina Têxtil")
    adapter = InMemoryERPAdapter(
        skus=[SKU, DA_TELA],
        fornecedores=[katrina],
        fornecedores_por_sku={s.sku_code: [make_fornecedor_sku(katrina)] for s in (SKU, DA_TELA)},
        estoques={SKU.sku_code: make_estoque(disponivel=40), DA_TELA.sku_code: make_estoque(disponivel=30)},
        vendas=[
            make_venda(s, datetime(2026, mes, 5, tzinfo=UTC), 100) for s in (SKU, DA_TELA) for mes in range(3, 9)
        ],
    )
    politicas = InMemoryPoliticaCompraRepositorio()
    redator = redator or RedatorGravador()
    registros = InMemoryRegistrosDecisao()
    app.dependency_overrides[get_registros_decisao] = lambda: registros
    app.dependency_overrides[get_erp_adapter] = lambda: adapter
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: politicas
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_trechos_repositorio] = lambda: trechos
    app.dependency_overrides[get_redator] = lambda: redator
    if decisao is not None:
        app.dependency_overrides[get_decision_model] = lambda: decisao
    return registros


def jev(entendimento: Entendimento, **kwargs: object) -> InMemoryDecisionModel:
    return InMemoryDecisionModel(entendimento_padrao=entendimento, modelo="jev-1.13.0", **kwargs)


def test_chat_responde_a_situacao_do_sku(client: TestClient) -> None:
    registros = preparar(
        jev(
            make_entendimento(
                "situacao_sku",
                0.93,
                probabilidades_intencao={"situacao_sku": 0.93, "sugestao_compra": 0.07},
                modelo="jev-1.13.0",
            )
        ),
        RedatorGravador("A TBC-BEGE-70140-01 tem 40 unidades."),
    )

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 200
    body = response.json()
    [ficha] = body.pop("fichas")
    registro_id = body.pop("registro_id")
    assert ficha["sku_code"] == "TBC-BEGE-70140-01"
    assert ficha["estoque"]["quantidade_disponivel"] == 40
    assert body == {
        "resposta": "A TBC-BEGE-70140-01 tem 40 unidades.",
        "acao": "respondeu",
        "faixa": "alta",
        "entendimento": {
            "intencao": {
                "escolha": "situacao_sku",
                "confianca": 0.93,
                "probabilidades": {"situacao_sku": 0.93, "sugestao_compra": 0.07},
            },
            "produto": {"escolha": "nenhum", "confianca": 0.95, "probabilidades": {"nenhum": 0.95}},
            "modelo": "jev-1.13.0",
        },
        "identificacao": {
            "skus": ["TBC-BEGE-70140-01"],
            "total_skus": 1,
            "origem": "codigo",
            "produto": None,
            "candidatos": [],
        },
        "sugestoes": [],
        "trechos": [],
        "conflitos": [],
        "citacoes": [],
        "redator": "gravador",
    }
    [registro] = registros.listar(10)
    assert UUID(registro_id) == registro.id


def test_chat_devolve_os_trechos_e_os_conflitos_que_foram_ao_redator(client: TestClient) -> None:
    preparar(
        jev(
            make_entendimento("politica_ou_fornecedor", 0.9),
            padrao={"relevante": 0.9, "tem_evidencia": 0.9},
            conflitos={("contratos/katrina.md#prazos", "reunioes/q1.md#katrina"): 0.62},
        )
    )

    response = client.post("/chat", json={"pergunta": "lead time da Katrina"})

    assert response.status_code == 200
    body = response.json()
    assert body["identificacao"] is None
    assert {t["id"] for t in body["trechos"]} == {"contratos/katrina.md#prazos", "reunioes/q1.md#katrina"}
    assert body["trechos"][0]["classificacao"] == "aceito"
    assert body["trechos"][0]["avaliacao"]["relevante"] == 0.9
    [conflito] = body["conflitos"]
    assert conflito["probabilidade"] == 0.62


def test_esclarecimento_vem_sem_redator(client: TestClient) -> None:
    redator = RedatorGravador()
    preparar(jev(make_entendimento("situacao_sku", 0.3)), redator)

    response = client.post("/chat", json={"pergunta": "hmm"})

    assert response.status_code == 200
    assert response.json()["acao"] == "pediu_esclarecimento"
    assert response.json()["redator"] is None
    assert redator.chamadas == []


@pytest.mark.parametrize(
    "corpo",
    [
        pytest.param({}, id="sem-pergunta"),
        pytest.param({"pergunta": ""}, id="pergunta-vazia"),
        pytest.param({"pergunta": "  \n\t "}, id="pergunta-so-com-espacos"),
        pytest.param({"pergunta": "x" * 1001}, id="pergunta-com-1001-caracteres"),
    ],
)
def test_pergunta_fora_do_intervalo_da_422(client: TestClient, corpo: dict[str, str]) -> None:
    preparar(jev(make_entendimento()))

    assert client.post("/chat", json=corpo).status_code == 422


def test_pergunta_com_1000_caracteres_e_aceita(client: TestClient) -> None:
    preparar(jev(make_entendimento()))

    assert client.post("/chat", json={"pergunta": "x" * 1000}).status_code == 200


def test_jev_indisponivel_da_503(client: TestClient) -> None:
    preparar(jev(make_entendimento(), falhar_entendimento=True))

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 503
    assert response.json()["detail"]


def test_sem_jev_key_da_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JEV_KEY", "")
    preparar()

    response = client.post("/chat", json={"pergunta": PERGUNTA})

    assert response.status_code == 503
    assert "JEV_KEY" in response.json()["detail"]


def test_registros_mostram_as_perguntas_respondidas_da_mais_recente(client: TestClient) -> None:
    preparar(
        jev(
            make_entendimento(
                "situacao_sku",
                0.93,
                probabilidades_intencao={"situacao_sku": 0.93, "sugestao_compra": 0.07},
                modelo="jev-1.13.0",
            )
        ),
        RedatorGravador("A TBC-BEGE-70140-01 tem 40 unidades."),
    )
    primeira = client.post("/chat", json={"pergunta": PERGUNTA}).json()
    segunda = client.post("/chat", json={"pergunta": "Como tá o estoque?"}).json()

    response = client.get("/chat/registros")

    assert response.status_code == 200
    recente, antigo = response.json()
    assert recente["id"] == segunda["registro_id"]
    assert recente["acao"] == "pediu_esclarecimento"
    assert recente["redator"] is None
    assert antigo["id"] == primeira["registro_id"]
    datetime.fromisoformat(antigo.pop("criado_em"))
    assert antigo.pop("duracao_ms") >= 0
    assert antigo == {
        "id": primeira["registro_id"],
        "pergunta": PERGUNTA,
        "intencao": "situacao_sku",
        "confianca": 0.93,
        "faixa": "alta",
        "acao": "respondeu",
        "skus": ["TBC-BEGE-70140-01"],
        "entendimento": primeira["entendimento"],
        "trechos": [],
        "redator": "gravador",
        "resposta": "A TBC-BEGE-70140-01 tem 40 unidades.",
        "sinais": [],
        "citacoes": [],
        "sku_em_contexto": None,
    }


def test_registros_respeitam_o_limite(client: TestClient) -> None:
    preparar(jev(make_entendimento("fora_de_escopo", 0.95)))
    for i in range(3):
        client.post("/chat", json={"pergunta": f"pergunta {i}"})

    response = client.get("/chat/registros", params={"limite": 2})

    assert response.status_code == 200
    assert [r["pergunta"] for r in response.json()] == ["pergunta 2", "pergunta 1"]


def test_registros_sem_pergunta_devolvem_lista_vazia(client: TestClient) -> None:
    preparar()

    response = client.get("/chat/registros")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("limite", [0, 101])
def test_limite_fora_do_intervalo_da_422(client: TestClient, limite: int) -> None:
    preparar()

    assert client.get("/chat/registros", params={"limite": limite}).status_code == 422


def test_jev_indisponivel_nao_grava_registro(client: TestClient) -> None:
    registros = preparar(jev(make_entendimento(), falhar_entendimento=True))

    assert client.post("/chat", json={"pergunta": PERGUNTA}).status_code == 503
    assert registros.listar(10) == []


def test_chat_de_sugestao_devolve_os_sinais_e_as_citacoes_e_grava_os_dois(client: TestClient) -> None:
    lead_time = "reunioes/q1.md#katrina"
    registros = preparar(
        jev(
            make_entendimento("sugestao_compra", 0.95),
            padrao={"relevante": 0.9, "tem_evidencia": 0.9},
            sinais={lead_time: {"atraso_do_fornecedor": 0.97}},
            citacoes={lead_time: make_relacao("sustenta", 0.96)},
        ),
        RedatorGravador(f"A Katrina atrasa [{lead_time}]. O contrato diz 30 dias [contratos/katrina.md#prazos]."),
    )

    response = client.post("/chat", json={"pergunta": "Quanto comprar do TBC-BEGE-70140-01?"})

    assert response.status_code == 200
    body = response.json()
    [sugestao] = body["sugestoes"]
    assert sugestao["sugestao"]["sku_code"] == "TBC-BEGE-70140-01"
    assert sugestao["sinais"] == [
        {
            "tipo": "atraso_do_fornecedor",
            "mensagem": "Os documentos relatam atraso de entrega da Katrina Têxtil.",
            "trechos": [lead_time],
            "probabilidade": 0.97,
        }
    ]
    assert body["citacoes"] == [
        {"trecho_id": lead_time, "afirmacao": "A Katrina atrasa.", "veredito": "confirmada", "confianca": 0.96},
        {
            "trecho_id": "contratos/katrina.md#prazos",
            "afirmacao": "O contrato diz 30 dias.",
            "veredito": "sem_suporte",
            "confianca": 1.0,
        },
    ]
    assert body["resposta"].endswith("[contratos/katrina.md#prazos - não confirmada].")

    [registro] = client.get("/chat/registros").json()
    assert registro["sinais"] == [{"sku_code": "TBC-BEGE-70140-01", "sinais": sugestao["sinais"]}]
    assert registro["citacoes"] == body["citacoes"]
    assert registros.listar(1)[0].citacoes[0].veredito == "confirmada"


def test_chat_de_sugestao_com_o_jev_fora_do_ar_nos_sinais_devolve_e_grava_sinais_nulos(client: TestClient) -> None:
    preparar(
        jev(
            make_entendimento("sugestao_compra", 0.95),
            padrao={"relevante": 0.9, "tem_evidencia": 0.9},
            falhar_sinais=True,
        ),
        RedatorGravador("Compre 120 unidades."),
    )

    response = client.post("/chat", json={"pergunta": "Quanto comprar do TBC-BEGE-70140-01?"})

    assert response.status_code == 200
    [sugestao] = response.json()["sugestoes"]
    assert sugestao["sinais"] is None
    [registro] = client.get("/chat/registros").json()
    assert registro["sinais"] == [{"sku_code": "TBC-BEGE-70140-01", "sinais": None}]


def _pergunta_na_tela(client: TestClient, pergunta: str, sku_code: str | None = DA_TELA.sku_code) -> dict:
    response = client.post("/chat", json={"pergunta": pergunta, "sku_code": sku_code})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("intencao", ["situacao_sku", "sugestao_compra"])
def test_pergunta_sem_produto_na_tela_do_sku_usa_o_sku_da_tela(client: TestClient, intencao: Intencao) -> None:
    redator = RedatorGravador("Está acabando porque vende 100 por mês.")
    preparar(jev(make_entendimento(intencao, 0.93)), redator)

    body = _pergunta_na_tela(client, "Por que está acabando?")

    assert body["identificacao"] == {
        "skus": [DA_TELA.sku_code],
        "total_skus": 1,
        "origem": "contexto",
        "produto": None,
        "candidatos": [],
    }
    assert [f["sku_code"] for f in body["fichas"]] + [s["sugestao"]["sku_code"] for s in body["sugestoes"]] == [
        DA_TELA.sku_code
    ]
    [(_, contexto)] = redator.chamadas
    assert f"o comprador está na tela do SKU {DA_TELA.sku_code}" in contexto


def test_produto_citado_tem_precedencia_sobre_o_sku_da_tela(client: TestClient) -> None:
    preparar(jev(make_entendimento("situacao_sku", 0.93)))

    body = _pergunta_na_tela(client, PERGUNTA)

    assert body["identificacao"]["skus"] == [SKU.sku_code]
    assert body["identificacao"]["origem"] == "codigo"
    assert [f["sku_code"] for f in body["fichas"]] == [SKU.sku_code]


def test_politica_ou_fornecedor_ignora_o_sku_da_tela(client: TestClient) -> None:
    redator = RedatorGravador("O lead time da Katrina é de 45 dias.")
    preparar(
        jev(make_entendimento("politica_ou_fornecedor", 0.93), padrao={"relevante": 0.9, "tem_evidencia": 0.9}),
        redator,
    )

    body = _pergunta_na_tela(client, "Qual o lead time da Katrina?")

    assert body["identificacao"] is None
    assert body["fichas"] == []
    [(_, contexto)] = redator.chamadas
    assert DA_TELA.sku_code not in contexto


def test_sem_sku_na_tela_o_chat_pede_esclarecimento_como_antes(client: TestClient) -> None:
    preparar(jev(make_entendimento("situacao_sku", 0.93)))

    body = _pergunta_na_tela(client, "Por que está acabando?", sku_code=None)

    assert body["acao"] == "pediu_esclarecimento"
    assert body["identificacao"]["origem"] == "nenhum"


def test_registro_grava_o_sku_da_tela(client: TestClient) -> None:
    registros = preparar(jev(make_entendimento("situacao_sku", 0.93)))

    _pergunta_na_tela(client, PERGUNTA)
    _pergunta_na_tela(client, "Por que está acabando?", sku_code=None)

    sem_tela, na_tela = registros.listar(10)
    assert na_tela.sku_em_contexto == DA_TELA.sku_code
    assert na_tela.skus == [SKU.sku_code]
    assert sem_tela.sku_em_contexto is None
    recente, antigo = client.get("/chat/registros").json()
    assert (recente["sku_em_contexto"], antigo["sku_em_contexto"]) == (None, DA_TELA.sku_code)


def test_sku_da_tela_desconhecido_responde_404_sem_registro(client: TestClient) -> None:
    registros = preparar(jev(make_entendimento("situacao_sku", 0.93)))

    response = client.post("/chat", json={"pergunta": "Por que está acabando?", "sku_code": "NAO-EXISTE"})

    assert response.status_code == 404
    assert registros.listar(10) == []


def test_registro_grava_quem_perguntou(client: TestClient, usuario_logado: Usuario) -> None:
    registros = preparar(jev(make_entendimento("situacao_sku", 0.93)))

    client.post("/chat", json={"pergunta": PERGUNTA})

    assert [r.usuario_id for r in registros.listar(10)] == [usuario_logado.id]
