"""Testes HTTP dos avisos da equipe de vendas (`/avisos`, `/skus/{sku}/avisos`), da
busca de SKUs da página de aviso e do efeito do aviso no painel. Cenário em
`cenario_painel.py`."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import (
    AGORA,
    INATIVO,
    MAIS_URGENTE,
    PISO,
    SEM_FORNECEDOR,
    SOBRANDO,
    URGENTE,
    avisar,
    client,  # noqa: F401 (fixture)
    codigos,
    montar_erp,
    painel,
    preparar,
)
from tests.fakes import make_sku


def test_aviso_valido_responde_201_e_fica_aberto(client: TestClient) -> None:
    cenario = preparar()

    aviso = avisar(client, SOBRANDO, "vendendo_muito", comentario="  Cliente X quer 200 peças. ")

    assert aviso == {
        "id": aviso["id"],
        "sku_code": SOBRANDO.sku_code,
        "tipo": "vendendo_muito",
        "comentario": "Cliente X quer 200 peças.",
        "avisado_por": "Joana",
        "criado_em": "2026-10-01T09:00:00Z",
    }
    assert [str(a.id) for a in cenario.avisos.listar()] == [aviso["id"]]
    assert client.get(f"/skus/{SOBRANDO.sku_code}/avisos").json() == [aviso]


def test_avisos_abertos_vem_do_mais_recente_para_o_mais_antigo(client: TestClient) -> None:
    cenario = preparar()
    primeiro = avisar(client, URGENTE)
    cenario.relogio.avancar(hours=2)
    segundo = avisar(client, URGENTE, "vendendo_muito", avisado_por="Bia")

    abertos = client.get(f"/skus/{URGENTE.sku_code}/avisos").json()

    assert [a["id"] for a in abertos] == [segundo["id"], primeiro["id"]]
    assert client.get(f"/skus/{PISO.sku_code}/avisos").json() == []


def test_comentario_em_branco_vira_nulo(client: TestClient) -> None:
    preparar()

    assert avisar(client, URGENTE, comentario="   ")["comentario"] is None


def test_aviso_de_sku_inexistente_responde_404(client: TestClient) -> None:
    preparar()

    response = client.post("/avisos", json={"sku_code": "NAO-EXISTE", "tipo": "acabou", "avisado_por": "Joana"})

    assert response.status_code == 404
    assert client.get("/skus/NAO-EXISTE/avisos").status_code == 404


def test_aviso_de_sku_inativo_responde_422_e_nao_grava(client: TestClient) -> None:
    cenario = preparar()

    response = client.post("/avisos", json={"sku_code": INATIVO.sku_code, "tipo": "acabou", "avisado_por": "Joana"})

    assert response.status_code == 422
    assert "inativo" in response.json()["detail"]
    assert cenario.avisos.listar() == []


@pytest.mark.parametrize(
    "corpo",
    [
        {"tipo": "faltando", "avisado_por": "Joana"},
        {"tipo": "acabou", "avisado_por": "   "},
        {"tipo": "acabou"},
    ],
    ids=["tipo-invalido", "nome-em-branco", "sem-nome"],
)
def test_aviso_invalido_responde_422(client: TestClient, corpo: dict) -> None:
    cenario = preparar()

    response = client.post("/avisos", json={"sku_code": URGENTE.sku_code, **corpo})

    assert response.status_code == 422
    assert cenario.avisos.listar() == []


def test_sku_com_aviso_e_sem_motivo_entra_no_primeiro_grupo_do_painel(client: TestClient) -> None:
    preparar()
    avisar(client, SOBRANDO, "vendendo_muito", avisado_por="Bia")

    alertas = painel(client)["alertas"]

    # Os com aviso ou ruptura, pela cobertura na chegada sem a compra: -0,8, -0,5 e 8,0.
    assert codigos(alertas) == [
        MAIS_URGENTE.sku_code,
        URGENTE.sku_code,
        SOBRANDO.sku_code,
        PISO.sku_code,
        SEM_FORNECEDOR.sku_code,
    ]
    sobrando = alertas[2]
    assert sobrando["motivos"] == []
    assert sobrando["so_por_aviso"] is True
    assert sobrando["avisos_abertos"] == 1
    assert sobrando["ultimo_aviso"]["tipo"] == "vendendo_muito"
    assert sobrando["ultimo_aviso"]["avisado_por"] == "Bia"


def test_aviso_de_sku_com_motivo_sobe_para_o_primeiro_grupo_e_conta_os_avisos(client: TestClient) -> None:
    cenario = preparar()
    avisar(client, PISO)
    cenario.relogio.avancar(minutes=5)
    avisar(client, PISO, "vendendo_muito", avisado_por="Bia")

    alertas = painel(client)["alertas"]

    # PISO tem 0,5 mês na chegada sem a compra: vai depois das rupturas, mas no primeiro grupo.
    assert codigos(alertas)[:3] == [MAIS_URGENTE.sku_code, URGENTE.sku_code, PISO.sku_code]
    piso = alertas[2]
    assert piso["so_por_aviso"] is False
    assert piso["avisos_abertos"] == 2
    assert piso["ultimo_aviso"]["avisado_por"] == "Bia"


def test_busca_sem_acento_nem_maiuscula_acha_o_sku(client: TestClient) -> None:
    preparar()

    response = client.get("/skus", params={"busca": "LENCOL casal"})

    assert response.status_code == 200
    assert response.json() == [
        {"sku_code": SEM_FORNECEDOR.sku_code, "produto_nome": "Lençol Casal", "cor": "branco", "tamanho": "casal"}
    ]


def test_busca_exige_todas_as_palavras_e_ordena_por_produto_cor_e_tamanho(client: TestClient) -> None:
    preparar()

    encontrados = client.get("/skus", params={"busca": "toalha 70x140"}).json()

    assert [(s["produto_nome"], s["cor"]) for s in encontrados] == [
        ("Toalha Banho Conforto", cor) for cor in ["azul", "bege", "branco", "cinza", "rosa", "verde"]
    ]
    assert client.get("/skus", params={"busca": "toalha casal"}).json() == []


def test_busca_ignora_sku_inativo_e_acha_pelo_codigo(client: TestClient) -> None:
    preparar()

    assert client.get("/skus", params={"busca": "pret"}).json() == []
    assert [s["sku_code"] for s in client.get("/skus", params={"busca": "tbc-azul"}).json()] == [
        MAIS_URGENTE.sku_code
    ]


def test_busca_traz_no_maximo_20(client: TestClient) -> None:
    muitos = [make_sku(f"FR-{i:02d}", produto_nome="Fronha Lisa", cor=f"cor {i:02d}") for i in range(25)]
    preparar(erp=montar_erp(muitos))

    encontrados = client.get("/skus", params={"busca": "fronha"}).json()

    assert [s["cor"] for s in encontrados] == [f"cor {i:02d}" for i in range(20)]


@pytest.mark.parametrize("busca", ["", "a"], ids=["vazia", "uma-letra"])
def test_busca_curta_demais_responde_422(client: TestClient, busca: str) -> None:
    preparar()

    assert client.get("/skus", params={"busca": busca}).status_code == 422


def test_criado_em_vem_do_relogio(client: TestClient) -> None:
    cenario = preparar()
    cenario.relogio.avancar(days=1)

    assert avisar(client, URGENTE)["criado_em"] == AGORA.replace(day=2).isoformat().replace("+00:00", "Z")
