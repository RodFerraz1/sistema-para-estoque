"""Testes HTTP do mix de gôndola (`/reposicao/produtos`, `/reposicao/produtos/{id}/mix` e
`/reposicao/produtos/{id}/capacidade`) e da participação nas vendas na tela do SKU.

O relógio fica na segunda-feira mais recente, como no `test_reposicao.py`. As 5 cores do
Tapete Banheiro venderam a mesma quantidade em cada um dos últimos 30 dias abertos: marrom
10, cinza 5, azul 3, bege 2 e branco 1 por dia (de 21 por dia, o marrom faz 48% e o branco
5%). A política olha os últimos 30 dias abertos (`dias_mix_gondola`). O Pano de Mesa, com
duas cores, não vendeu nada. A `LOJA` vende todo dia aberto.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, time

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import BOA_VISTA, DEPENDENCIAS, Cenario, preparar
from src.api.tests.test_meus_avisos import como
from src.api.tests.test_reposicao import AGORA, dias_abertos
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.usuarios.dependencies import usuario_atual
from tests.fakes import make_estoque, make_fornecedor_sku, make_sku, make_usuario, make_venda


def tapete(codigo: str, cor: str) -> SKU:
    return make_sku(codigo, produto_nome="Tapete Banheiro", categoria="banho", cor=cor, tamanho="40x60")


MARROM = tapete("TAP-MARR-4060-01", "marrom")
CINZA = tapete("TAP-CINZ-4060-02", "cinza")
AZUL = tapete("TAP-AZUL-4060-03", "azul")
BEGE = tapete("TAP-BEGE-4060-04", "bege")
BRANCO = tapete("TAP-BRAN-4060-05", "branco")
TAPETES = [MARROM, CINZA, AZUL, BEGE, BRANCO]
POR_DIA = [(MARROM, 10), (CINZA, 5), (AZUL, 3), (BEGE, 2), (BRANCO, 1)]
PANO_PRETO = make_sku("PM-PRET-140-01", produto_nome="Pano de Mesa", categoria="mesa", cor="preto", tamanho="140")
PANO_AMARELO = make_sku("PM-AMAR-3040-01", produto_nome="Pano de Mesa", categoria="mesa", cor="amarelo", tamanho="30x40")
LOJA = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto", cor="branco")
RAFA = make_usuario("Rafa", papeis=["reposicao"])


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in (*DEPENDENCIAS, usuario_atual):
        app.dependency_overrides.pop(dependencia, None)


def vendeu_todo_dia(sku: SKU, por_dia: int, dias: int = 30) -> list:
    return [make_venda(sku, datetime.combine(d, time(15), tzinfo=UTC), por_dia) for d in dias_abertos(dias)]


def preparar_mix(disponiveis: dict[str, int] | None = None) -> Cenario:
    skus = [*TAPETES, PANO_PRETO, PANO_AMARELO, LOJA]
    disponiveis = disponiveis or {}
    erp = InMemoryERPAdapter(
        skus=skus,
        fornecedores=[BOA_VISTA],
        fornecedores_por_sku={s.sku_code: [make_fornecedor_sku(BOA_VISTA)] for s in skus},
        estoques={s.sku_code: make_estoque(disponivel=disponiveis.get(s.sku_code, 400)) for s in skus},
        vendas=[
            *(v for sku, q in POR_DIA for v in vendeu_todo_dia(sku, q)),
            *vendeu_todo_dia(LOJA, 6, 40),
        ],
    )
    cenario = preparar(erp=erp, dias_mix_gondola=30)
    cenario.relogio.agora = AGORA
    return cenario


def mix(client: TestClient, produto: SKU, **params: int) -> dict:
    response = client.get(f"/reposicao/produtos/{produto.produto_id}/mix", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def quantidades(resposta: dict) -> dict[str, int | None]:
    return {s["sku_code"]: s["quantidade"] for s in resposta["skus"]}


def test_com_12_lugares_o_marrom_ganha_mais_e_o_branco_ganha_ao_menos_uma(client: TestClient) -> None:
    preparar_mix()

    resposta = mix(client, MARROM, capacidade=12)

    assert resposta["produto_nome"] == "Tapete Banheiro"
    assert resposta["capacidade"] == 12
    assert [s["cor"] for s in resposta["skus"]] == ["marrom", "cinza", "azul", "bege", "branco"]
    assert [s["quantidade"] for s in resposta["skus"]] == [4, 3, 2, 2, 1]
    marrom, *_, branco = resposta["skus"]
    assert marrom["participacao"] == pytest.approx(10 / 21)
    assert marrom["venda_media_diaria"] == pytest.approx(10)
    assert marrom["disponivel"] == 400
    assert (branco["participacao"], branco["tamanho"]) == (pytest.approx(1 / 21), "40x60")


def test_com_menos_lugares_que_cores_as_pecas_vao_para_as_que_mais_vendem(client: TestClient) -> None:
    preparar_mix()

    assert quantidades(mix(client, MARROM, capacidade=3)) == {
        MARROM.sku_code: 1,
        CINZA.sku_code: 1,
        AZUL.sku_code: 1,
        BEGE.sku_code: 0,
        BRANCO.sku_code: 0,
    }


def test_nada_passa_do_disponivel_e_o_que_sobra_vai_para_a_proxima_cor_que_mais_vende(client: TestClient) -> None:
    preparar_mix({MARROM.sku_code: 2, BRANCO.sku_code: 0})

    assert quantidades(mix(client, MARROM, capacidade=12)) == {
        MARROM.sku_code: 2,
        CINZA.sku_code: 4,
        AZUL.sku_code: 3,
        BEGE.sku_code: 3,
        BRANCO.sku_code: 0,
    }


def test_sem_estoque_que_encha_a_gondola_a_soma_fica_no_disponivel(client: TestClient) -> None:
    preparar_mix({MARROM.sku_code: 3, CINZA.sku_code: 1, AZUL.sku_code: 0, BEGE.sku_code: 0, BRANCO.sku_code: 1})

    assert sum(q or 0 for q in quantidades(mix(client, MARROM, capacidade=12)).values()) == 5


def test_produto_sem_venda_divide_igual_entre_as_cores(client: TestClient) -> None:
    preparar_mix()

    resposta = mix(client, PANO_PRETO, capacidade=4)

    assert quantidades(resposta) == {PANO_AMARELO.sku_code: 2, PANO_PRETO.sku_code: 2}
    assert [s["participacao"] for s in resposta["skus"]] == [0, 0]


def test_sem_capacidade_vem_so_a_participacao(client: TestClient) -> None:
    preparar_mix()

    resposta = mix(client, MARROM)

    assert resposta["capacidade"] is None and resposta["capacidade_gravada"] is None
    assert set(quantidades(resposta).values()) == {None}
    assert [s["participacao"] for s in resposta["skus"]] == pytest.approx([10 / 21, 5 / 21, 3 / 21, 2 / 21, 1 / 21])
    assert resposta["dias_abertos"] == 30


def test_a_capacidade_gravada_e_reusada(client: TestClient) -> None:
    cenario = preparar_mix()
    como(cenario, RAFA)

    response = client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": 12})

    assert response.status_code == 200, response.text
    assert response.json()["capacidade"] == 12
    resposta = mix(client, MARROM)
    assert (resposta["capacidade"], resposta["capacidade_gravada"]) == (12, 12)
    assert sum(q or 0 for q in quantidades(resposta).values()) == 12
    digitada = mix(client, MARROM, capacidade=3)
    assert (digitada["capacidade"], digitada["capacidade_gravada"]) == (3, 12)


def test_vale_a_ultima_capacidade_gravada(client: TestClient) -> None:
    cenario = preparar_mix()
    como(cenario, RAFA)

    for capacidade in (12, 20):
        client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": capacidade})

    assert mix(client, MARROM)["capacidade_gravada"] == 20


@pytest.mark.parametrize("capacidade", [0, -1])
def test_capacidade_precisa_ser_maior_que_zero(client: TestClient, capacidade: int) -> None:
    preparar_mix()

    gravar = client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": capacidade})
    digitada = client.get(f"/reposicao/produtos/{MARROM.produto_id}/mix", params={"capacidade": capacidade})

    assert (gravar.status_code, digitada.status_code) == (422, 422)


def test_produto_sem_sku_ativo_e_404(client: TestClient) -> None:
    preparar_mix()
    sem_sku = make_sku("XX-0001", produto_nome="Produto que não existe")

    gravar = client.put(f"/reposicao/produtos/{sem_sku.produto_id}/capacidade", json={"capacidade": 5})
    ver = client.get(f"/reposicao/produtos/{sem_sku.produto_id}/mix")

    assert (gravar.status_code, ver.status_code) == (404, 404)


def test_busca_de_produto_pelo_nome_com_a_capacidade_gravada(client: TestClient) -> None:
    cenario = preparar_mix()
    como(cenario, RAFA)
    client.put(f"/reposicao/produtos/{MARROM.produto_id}/capacidade", json={"capacidade": 12})

    response = client.get("/reposicao/produtos", params={"busca": "tapete"})

    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "produto_id": str(MARROM.produto_id),
            "produto_nome": "Tapete Banheiro",
            "categoria": "banho",
            "skus": 5,
            "capacidade": 12,
        }
    ]


def test_sem_busca_lista_todos_os_produtos_pelo_nome(client: TestClient) -> None:
    preparar_mix()

    response = client.get("/reposicao/produtos")

    assert [p["produto_nome"] for p in response.json()] == ["Pano de Mesa", "Tapete Banheiro", "Toalha Banho Conforto"]
    assert response.json()[0]["capacidade"] is None


def test_a_busca_acha_o_produto_pela_cor_de_um_sku(client: TestClient) -> None:
    preparar_mix()

    response = client.get("/reposicao/produtos", params={"busca": "pano amarelo"})

    assert [p["produto_nome"] for p in response.json()] == ["Pano de Mesa"]


def test_os_cards_do_painel_do_repositor_trazem_o_produto(client: TestClient) -> None:
    from src.api.tests.test_reposicao import TAPETE, preparar_reposicao, vendas

    preparar_reposicao({TAPETE.sku_code: 400}, vendas(TAPETE, 10, 5, 0))

    [card] = client.get("/reposicao/painel").json()["quedas_de_venda"]

    assert card["produto_id"] == str(TAPETE.produto_id)


def test_o_comprador_ve_a_participacao_e_o_produto_na_tela_do_sku(client: TestClient) -> None:
    cenario = preparar_mix()
    como(cenario, make_usuario("Carla", papeis=["comprador"]))

    analise = client.get(f"/skus/{BRANCO.sku_code}/analise")
    resposta = mix(client, BRANCO)

    assert analise.json()["produto_id"] == str(BRANCO.produto_id)
    assert resposta["skus"][-1]["sku_code"] == BRANCO.sku_code
    assert resposta["skus"][-1]["participacao"] == pytest.approx(1 / 21)
