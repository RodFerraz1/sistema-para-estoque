"""Testes HTTP dos avisos da equipe de vendas (`/avisos`, `/skus/{sku}/avisos`), da
busca de SKUs da página de aviso e do efeito do aviso no painel. Cenário em
`cenario_painel.py`."""
from __future__ import annotations

from uuid import uuid4

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
    ZERADO,
    avisar,
    client,  # noqa: F401 (fixture)
    codigos,
    montar_erp,
    painel,
    preparar,
)
from src.painel.schemas import Aviso
from src.usuarios.schemas import Usuario
from tests.fakes import make_sku


def test_aviso_valido_responde_201_e_fica_aberto(client: TestClient, usuario_logado: Usuario) -> None:
    cenario = preparar()

    aviso = avisar(client, SOBRANDO, "vendendo_muito", comentario="  Cliente X quer 200 peças. ")

    assert aviso == {
        "id": aviso["id"],
        "sku_code": SOBRANDO.sku_code,
        "tipo": "vendendo_muito",
        "comentario": "Cliente X quer 200 peças.",
        "avisado_por": usuario_logado.nome,
        "criado_em": "2026-10-01T09:00:00Z",
    }
    [gravado] = cenario.avisos.listar()
    assert (str(gravado.id), gravado.usuario_id) == (aviso["id"], usuario_logado.id)
    assert client.get(f"/skus/{SOBRANDO.sku_code}/avisos").json() == [aviso]


def test_avisos_abertos_vem_do_mais_recente_para_o_mais_antigo(client: TestClient) -> None:
    cenario = preparar()
    primeiro = avisar(client, URGENTE)
    cenario.relogio.avancar(hours=2)
    segundo = avisar(client, URGENTE, "vendendo_muito")

    abertos = client.get(f"/skus/{URGENTE.sku_code}/avisos").json()

    assert [a["id"] for a in abertos] == [segundo["id"], primeiro["id"]]
    assert client.get(f"/skus/{PISO.sku_code}/avisos").json() == []


def test_comentario_em_branco_vira_nulo(client: TestClient) -> None:
    preparar()

    assert avisar(client, URGENTE, comentario="   ")["comentario"] is None


def test_aviso_de_sku_inexistente_responde_404(client: TestClient) -> None:
    preparar()

    response = client.post("/avisos", json={"sku_code": "NAO-EXISTE", "tipo": "acabou"})

    assert response.status_code == 404
    assert client.get("/skus/NAO-EXISTE/avisos").status_code == 404


def test_aviso_de_sku_inativo_responde_422_e_nao_grava(client: TestClient) -> None:
    cenario = preparar()

    response = client.post("/avisos", json={"sku_code": INATIVO.sku_code, "tipo": "acabou"})

    assert response.status_code == 422
    assert "inativo" in response.json()["detail"]
    assert cenario.avisos.listar() == []


def test_aviso_grava_o_usuario_logado_e_ignora_nome_no_corpo(client: TestClient, usuario_logado: Usuario) -> None:
    cenario = preparar()

    aviso = avisar(client, URGENTE, avisado_por="Outra Pessoa")

    assert aviso["avisado_por"] == usuario_logado.nome
    assert [a.usuario_id for a in cenario.avisos.listar()] == [usuario_logado.id]


def test_aviso_antigo_continua_com_o_nome_digitado(client: TestClient) -> None:
    cenario = preparar()
    antigo = Aviso(
        id=uuid4(),
        sku_code=URGENTE.sku_code,
        tipo="acabou",
        comentario=None,
        avisado_por="Joana digitou",
        usuario_id=None,
        criado_em=AGORA.replace(hour=8),
    )
    cenario.avisos.gravar(antigo)
    novo = avisar(client, URGENTE, "vendendo_muito")

    abertos = client.get(f"/skus/{URGENTE.sku_code}/avisos").json()

    assert [(a["id"], a["avisado_por"]) for a in abertos] == [
        (novo["id"], "Pessoa Teste"),
        (str(antigo.id), "Joana digitou"),
    ]


@pytest.mark.parametrize("corpo", [{"tipo": "faltando"}, {}], ids=["tipo-invalido", "sem-tipo"])
def test_aviso_invalido_responde_422(client: TestClient, corpo: dict) -> None:
    cenario = preparar()

    response = client.post("/avisos", json={"sku_code": URGENTE.sku_code, **corpo})

    assert response.status_code == 422
    assert cenario.avisos.listar() == []


def test_sku_com_aviso_e_sem_motivo_entra_no_primeiro_grupo_do_painel(client: TestClient) -> None:
    preparar()
    aviso = avisar(client, SOBRANDO, "vendendo_muito")

    alertas = painel(client)["alertas"]

    # Primeiro os com aviso; depois os em ruptura, do zerado ao que segura mais dias.
    assert codigos(alertas) == [
        SOBRANDO.sku_code,
        ZERADO.sku_code,
        SEM_FORNECEDOR.sku_code,
        MAIS_URGENTE.sku_code,
        URGENTE.sku_code,
        PISO.sku_code,
    ]
    sobrando = alertas[0]
    assert sobrando["motivos"] == []
    assert sobrando["so_por_aviso"] is True
    assert sobrando["avisos_abertos"] == 1
    assert sobrando["ultimo_aviso"] == aviso


def test_aviso_de_sku_com_motivo_sobe_para_o_primeiro_grupo_e_conta_os_avisos(client: TestClient) -> None:
    cenario = preparar()
    avisar(client, PISO)
    cenario.relogio.avancar(minutes=5)
    ultimo = avisar(client, PISO, "vendendo_muito")

    alertas = painel(client)["alertas"]

    assert codigos(alertas)[:2] == [PISO.sku_code, ZERADO.sku_code]
    piso = alertas[0]
    assert piso["so_por_aviso"] is False
    assert piso["avisos_abertos"] == 2
    assert piso["ultimo_aviso"] == ultimo


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
        ("Toalha Banho Conforto", cor) for cor in ["azul", "bege", "branco", "cinza", "lilás", "rosa", "verde"]
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
