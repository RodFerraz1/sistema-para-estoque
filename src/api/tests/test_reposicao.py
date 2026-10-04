"""Testes HTTP do painel do repositor (`/reposicao/painel`) e do selo "parou de vender" no
painel do comprador, com vendas diárias em memória e o relógio injetado.

O relógio fica na segunda-feira mais recente, às 9h. A loja abre de segunda a sábado: no
domingo ninguém vende. A janela observada da política padrão é de 2 dias abertos (sexta e
sábado) e a venda diária base é a média dos 28 dias abertos anteriores. O giro mensal sai
das mesmas vendas diárias, para o disponível zero ser ruptura no painel do comprador. A
`LOJA` vende todo dia aberto, para a loja abrir mesmo quando o SKU do teste não vende.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.tests.cenario_painel import BOA_VISTA, Cenario, atrasar, codigos, painel, preparar
from src.catalog.schemas import SKU
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.main import app
from src.usuarios.schemas import Papel
from tests.fakes import make_estoque, make_fornecedor_sku, make_sku, make_venda

DOMINGO = 6
TAPETE = make_sku("TAP-MARR-4060-01", produto_nome="Tapete Banheiro", categoria="banho", cor="marrom", tamanho="40x60")
TAPETE_CINZA = make_sku("TAP-CINZ-4060-02", produto_nome="Tapete Banheiro", categoria="banho", cor="cinza", tamanho="40x60")
TOALHA = make_sku("TBC-AZUL-70140-01", produto_nome="Toalha Banho Conforto", cor="azul")
RARO = make_sku("PM-PRET-140-01", produto_nome="Pano de Mesa", categoria="mesa", cor="preto", tamanho="140")
REGULAR = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege")
ZERADO = make_sku("PM-AMAR-3040-01", produto_nome="Pano de Mesa", categoria="mesa", cor="amarelo", tamanho="30x40")
LOJA = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto", cor="branco")


def segunda_mais_recente() -> datetime:
    hoje = datetime.now(UTC).date()
    return datetime.combine(hoje - timedelta(days=hoje.weekday()), time(9), tzinfo=UTC)


AGORA = segunda_mais_recente()


def dias_abertos(quantos: int, *, antes_de: date | None = None) -> list[date]:
    """Os `quantos` dias de segunda a sábado antes de `antes_de` (hoje), do mais recente ao
    mais antigo."""
    dia = antes_de or AGORA.date()
    dias: list[date] = []
    while len(dias) < quantos:
        dia -= timedelta(days=1)
        if dia.weekday() != DOMINGO:
            dias.append(dia)
    return dias


def vendas(sku: SKU, base: float, *janela: int) -> list:
    """`janela` são as vendas dos últimos dias abertos, do mais antigo até o sábado; nos 40
    dias abertos antes deles o SKU vende `base` por dia em média (inteiros que somam isso)."""
    dias = dias_abertos(40 + len(janela))
    recentes = list(reversed(dias[: len(janela)]))
    lista = [make_venda(sku, datetime.combine(d, time(15), tzinfo=UTC), q) for d, q in zip(recentes, janela) if q]
    acumulado = 0.0
    for i, dia in enumerate(reversed(dias[len(janela) :])):
        quantidade = int(base * (i + 1)) - int(acumulado)
        acumulado += quantidade
        if quantidade:
            lista.append(make_venda(sku, datetime.combine(dia, time(15), tzinfo=UTC), quantidade))
    return lista


def montar_erp(disponiveis: dict[str, int], todas_as_vendas: list) -> InMemoryERPAdapter:
    skus = [TAPETE, TAPETE_CINZA, TOALHA, RARO, REGULAR, ZERADO, LOJA]
    return InMemoryERPAdapter(
        skus=skus,
        fornecedores=[BOA_VISTA],
        fornecedores_por_sku={s.sku_code: [make_fornecedor_sku(BOA_VISTA, preco_unitario_reais=2000)] for s in skus},
        estoques={s.sku_code: make_estoque(disponivel=disponiveis.get(s.sku_code, 500)) for s in skus},
        vendas=todas_as_vendas,
    )


def preparar_reposicao(disponiveis: dict[str, int] | None = None, *todas_as_vendas: list, **parametros: object) -> Cenario:
    lojas = [*todas_as_vendas, vendas(LOJA, 6, 6, 6)]
    cenario = preparar(erp=montar_erp(disponiveis or {}, [v for lista in lojas for v in lista]), **parametros)
    cenario.relogio.agora = AGORA
    return cenario


@pytest.fixture
def client() -> Iterator[TestClient]:
    from src.api.tests.cenario_painel import DEPENDENCIAS

    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def painel_do_repositor(client: TestClient, **filtros: str) -> list[dict]:
    response = client.get("/reposicao/painel", params=filtros)
    assert response.status_code == 200, response.text
    return response.json()["quedas_de_venda"]


def test_tapete_que_vendia_10_por_dia_e_vendeu_5_e_0_vai_para_o_repositor(client: TestClient) -> None:
    preparar_reposicao({TAPETE.sku_code: 400}, vendas(TAPETE, 10, 5, 0), vendas(REGULAR, 4, 4, 3))

    [tapete] = painel_do_repositor(client)

    assert tapete["sku_code"] == TAPETE.sku_code
    assert (tapete["produto_nome"], tapete["cor"], tapete["tamanho"]) == ("Tapete Banheiro", "marrom", "40x60")
    assert tapete["venda_diaria_base"] == pytest.approx(10)
    assert tapete["vendido_na_janela"] == 5
    assert [d["quantidade"] for d in tapete["ultimos_dias"]] == [5, 0]
    assert [d["dia"] for d in tapete["ultimos_dias"]] == [d.isoformat() for d in reversed(dias_abertos(2))]
    assert tapete["venda_perdida"] == pytest.approx(15)
    assert tapete["disponivel"] == 400


def test_sku_que_vende_pouco_e_ficou_dois_dias_sem_vender_nao_entra(client: TestClient) -> None:
    preparar_reposicao({}, vendas(RARO, 0.3, 0, 0), vendas(TAPETE, 10, 5, 0))

    assert codigos(painel_do_repositor(client)) == [TAPETE.sku_code]


def test_sem_a_venda_minima_dois_dias_sem_vender_ainda_e_normal_para_quem_vende_03_por_dia(
    client: TestClient,
) -> None:
    preparar_reposicao({}, vendas(RARO, 0.3, 0, 0), venda_diaria_minima_queda=0.1)

    assert painel_do_repositor(client) == []


def test_domingo_sem_venda_na_loja_nao_conta_como_dia_sem_venda(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TOALHA, 12, 12, 12))

    assert painel_do_repositor(client) == []


def test_domingo_conta_quando_a_loja_vendeu(client: TestClient) -> None:
    domingo = datetime.combine(AGORA.date() - timedelta(days=1), time(15), tzinfo=UTC)
    preparar_reposicao({}, vendas(TOALHA, 12, 12, 12), [make_venda(REGULAR, domingo, 3)])

    [toalha] = painel_do_repositor(client)

    assert toalha["sku_code"] == TOALHA.sku_code
    assert toalha["vendido_na_janela"] == 12
    assert [d["quantidade"] for d in toalha["ultimos_dias"]] == [12, 0]


def test_hoje_nao_entra_na_janela(client: TestClient) -> None:
    hoje_cedo = datetime.combine(AGORA.date(), time(8), tzinfo=UTC)
    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0), [make_venda(TAPETE, hoje_cedo, 30)])

    assert codigos(painel_do_repositor(client)) == [TAPETE.sku_code]


def test_quem_perde_mais_venda_vem_primeiro(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0), vendas(TAPETE_CINZA, 5, 0, 0), vendas(TOALHA, 30, 0, 10))

    itens = painel_do_repositor(client)

    assert codigos(itens) == [TOALHA.sku_code, TAPETE.sku_code, TAPETE_CINZA.sku_code]
    assert [i["venda_perdida"] for i in itens] == pytest.approx([50, 15, 10])


def test_sem_estoque_nao_vai_para_o_repositor_e_aparece_em_ruptura_com_o_selo(client: TestClient) -> None:
    preparar_reposicao({ZERADO.sku_code: 0}, vendas(ZERADO, 4, 0, 0), vendas(TAPETE, 10, 5, 0))

    assert codigos(painel_do_repositor(client)) == [TAPETE.sku_code]
    itens = {i["sku_code"]: i for i in painel(client)["alertas"]}
    assert itens[ZERADO.sku_code]["grupo"] == "em_ruptura"
    assert itens[ZERADO.sku_code]["parou_de_vender"] is True


def test_sem_estoque_e_com_entrega_atrasada_aparece_na_entrega_com_o_selo(client: TestClient) -> None:
    cenario = preparar_reposicao({ZERADO.sku_code: 0}, vendas(ZERADO, 4, 0, 0))
    atrasar(cenario, BOA_VISTA, (ZERADO, 50), prevista=AGORA.date() - timedelta(days=3))

    assert painel_do_repositor(client) == []
    [item] = [i for i in painel(client)["alertas"] if i["sku_code"] == ZERADO.sku_code]
    assert item["grupo"] == "entregas_atrasadas"
    assert item["parou_de_vender"] is True


def test_o_selo_so_vale_para_quem_parou_de_vender_sem_estoque(client: TestClient) -> None:
    preparar_reposicao(
        {ZERADO.sku_code: 0, REGULAR.sku_code: 0, TAPETE.sku_code: 30},
        vendas(ZERADO, 4, 0, 0),
        vendas(REGULAR, 4, 4, 3),
        vendas(TAPETE, 10, 5, 0),
    )

    selos = {i["sku_code"]: i["parou_de_vender"] for i in painel(client)["alertas"]}

    assert selos[ZERADO.sku_code] is True
    assert selos[REGULAR.sku_code] is False
    assert selos[TAPETE.sku_code] is False


def test_busca_e_categoria_filtram_o_painel_do_repositor(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0), vendas(TAPETE_CINZA, 5, 0, 0), vendas(TOALHA, 30, 0, 10))

    assert codigos(painel_do_repositor(client, busca="tapete marrom")) == [TAPETE.sku_code]
    assert codigos(painel_do_repositor(client, categoria="banho")) == [TAPETE.sku_code, TAPETE_CINZA.sku_code]
    assert painel_do_repositor(client, busca="tapete", categoria="felpudo") == []


def test_politica_com_janela_maior_olha_mais_dias_abertos(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TAPETE, 10, 10, 10, 5, 0), dias_observados_queda=4)

    [tapete] = painel_do_repositor(client)

    assert [d["quantidade"] for d in tapete["ultimos_dias"]] == [10, 10, 5, 0]
    assert tapete["venda_perdida"] == pytest.approx(15)


@pytest.mark.papeis("reposicao")
def test_o_repositor_ve_o_painel(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0))

    assert codigos(painel_do_repositor(client)) == [TAPETE.sku_code]


@pytest.mark.parametrize("papel", ["comprador", "vendas", "admin"])
def test_outros_papeis_nao_veem_o_painel_do_repositor(client: TestClient, papel: Papel) -> None:
    from src.usuarios.dependencies import usuario_atual
    from tests.fakes import make_usuario

    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0))
    app.dependency_overrides[usuario_atual] = lambda: make_usuario(papeis=[papel])

    assert client.get("/reposicao/painel").status_code == 403



@pytest.mark.papeis("reposicao")
def test_o_repositor_le_as_categorias_para_filtrar(client: TestClient) -> None:
    preparar_reposicao({}, vendas(TAPETE, 10, 5, 0))

    response = client.get("/categorias")

    assert response.status_code == 200
    assert "banho" in response.json()
