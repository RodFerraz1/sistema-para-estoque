"""Cenário dos testes HTTP do painel de alertas, dos avisos e das decisões de compra:
ERP, política, repositórios do painel e relógio em memória.

Giro de 100 por mês (venda média diária de 3,33) nos seis meses fechados antes do atual e
fornecedor Boa Vista com lead time de 30 dias, R$ 20,00 a unidade e MOQ 48. Política padrão:
lead time ignorado, piso de alerta de 20 dias, piso de reposição de 30 dias e ciclo de 2 meses.
Em ruptura (abaixo de 20 dias): `ZERADO` (0 dias), `SEM_FORNECEDOR` (3 dias, sem cálculo),
`MAIS_URGENTE` (6 dias), `URGENTE` (15 dias) e `PISO` (15 dias, com 100 a caminho, sem compra).
`REGULAR` segura 45 dias e `SOBRANDO` 270. Com o lead time observado ligado, `URGENTE` e
`MAIS_URGENTE` acabam antes da compra chegar. Todos são da categoria `felpudo`, menos o
`SEM_FORNECEDOR` (`cama`) e o `INATIVO` (`mesa`). A Katrina também vende `ZERADO` e
`MAIS_URGENTE`, mais cara que a Boa Vista. Os episódios de alerta, os usuários, as
verificações de gôndola e os relógios das notificações e da reposição também ficam em
memória, com o mesmo relógio do painel.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from src.catalog.schemas import SKU, Fornecedor
from src.erp_adapter.dependencies import get_erp_adapter
from src.erp_adapter.in_memory import InMemoryERPAdapter, PedidoCompra
from src.erp_adapter.schemas import StatusPedidoCompra
from src.main import app
from src.notificacoes.dependencies import get_episodios_repositorio
from src.notificacoes.dependencies import get_relogio as get_relogio_das_notificacoes
from src.notificacoes.in_memory import InMemoryEpisodiosRepositorio
from src.painel.dependencies import (
    get_avisos_repositorio,
    get_cobrancas_repositorio,
    get_decisoes_repositorio,
    get_relogio,
)
from src.painel.in_memory import (
    InMemoryAvisosRepositorio,
    InMemoryCobrancasRepositorio,
    InMemoryDecisoesRepositorio,
)
from src.politica_compra.dependencies import get_politica_compra_repositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import PARAMETROS_V1
from src.reposicao.dependencies import get_relogio as get_relogio_da_reposicao
from src.reposicao.dependencies import get_verificacoes_repositorio
from src.reposicao.in_memory import InMemoryVerificacoesRepositorio
from src.usuarios.dependencies import get_usuarios_repositorio
from src.usuarios.in_memory import InMemoryUsuariosRepositorio
from tests.fakes import (
    RelogioFake,
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_item_pedido_compra,
    make_pedido_compra,
    make_sku,
    make_venda,
)

BOA_VISTA = make_fornecedor("Boa Vista Têxtil", lead_time_dias_contratado=30)
KATRINA = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=45)
ZERADO = make_sku("TBC-LILA-70140-01", produto_nome="Toalha Banho Conforto", cor="lilás")
URGENTE = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto", cor="branco")
MAIS_URGENTE = make_sku("TBC-AZUL-70140-01", produto_nome="Toalha Banho Conforto", cor="azul")
PISO = make_sku("TBC-ROSA-70140-01", produto_nome="Toalha Banho Conforto", cor="rosa")
SEM_FORNECEDOR = make_sku("LC-BRAN-CASAL-01", produto_nome="Lençol Casal", categoria="cama", tamanho="casal")
REGULAR = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege")
SOBRANDO = make_sku("TBC-VERD-70140-01", produto_nome="Toalha Banho Conforto", cor="verde")
INATIVO = make_sku("PM-PRET-140-01", produto_nome="Pano de Mesa", categoria="mesa", cor="preto", ativo=False)
QUEBRADO = make_sku("TBC-CINZ-70140-01", produto_nome="Toalha Banho Conforto", cor="cinza")
DISPONIVEIS = [
    (ZERADO, 0),
    (URGENTE, 50),
    (MAIS_URGENTE, 20),
    (PISO, 50),
    (SEM_FORNECEDOR, 10),
    (REGULAR, 150),
    (SOBRANDO, 900),
    (INATIVO, 10),
]
AGORA = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
DEPENDENCIAS = (
    get_erp_adapter,
    get_politica_compra_repositorio,
    get_avisos_repositorio,
    get_decisoes_repositorio,
    get_cobrancas_repositorio,
    get_relogio,
    get_episodios_repositorio,
    get_usuarios_repositorio,
    get_relogio_das_notificacoes,
    get_relogio_da_reposicao,
    get_verificacoes_repositorio,
)
ONTEM = date(2026, 9, 30)


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    for dependencia in DEPENDENCIAS:
        app.dependency_overrides.pop(dependencia, None)


def meses_fechados(quantos: int) -> list[datetime]:
    hoje = datetime.now(UTC)
    ano, mes = hoje.year, hoje.month
    datas = []
    for _ in range(quantos):
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        datas.append(datetime(ano, mes, 5, tzinfo=UTC))
    return datas


def montar_erp(skus: list[SKU] | None = None) -> InMemoryERPAdapter:
    a_caminho = make_pedido_compra(BOA_VISTA, "enviado")
    com_venda = [*(sku for sku, _ in DISPONIVEIS), QUEBRADO]
    return InMemoryERPAdapter(
        skus=skus or com_venda,
        fornecedores=[BOA_VISTA, KATRINA],
        fornecedores_por_sku={
            sku.sku_code: [
                make_fornecedor_sku(BOA_VISTA, preco_unitario_reais=2000, lead_time_dias_observado=30),
                *([make_fornecedor_sku(KATRINA, preco_unitario_reais=3000)] if sku in (ZERADO, MAIS_URGENTE) else []),
            ]
            for sku in com_venda
            if sku != SEM_FORNECEDOR
        },
        estoques={sku.sku_code: make_estoque(disponivel=d) for sku, d in DISPONIVEIS},
        vendas=[
            make_venda(sku, data, 100, key=f"{sku.sku_code}-{data:%Y-%m}")
            for sku in com_venda
            for data in meses_fechados(6)
        ],
        pedidos_compra=[a_caminho],
        itens_pedido_compra=[make_item_pedido_compra(a_caminho, PISO, quantidade=100)],
    )


@dataclass
class Cenario:
    erp: InMemoryERPAdapter
    politicas: InMemoryPoliticaCompraRepositorio
    avisos: InMemoryAvisosRepositorio
    decisoes: InMemoryDecisoesRepositorio
    cobrancas: InMemoryCobrancasRepositorio
    episodios: InMemoryEpisodiosRepositorio
    usuarios: InMemoryUsuariosRepositorio
    verificacoes: InMemoryVerificacoesRepositorio
    relogio: RelogioFake


def preparar(*, erp: InMemoryERPAdapter | None = None, **parametros: object) -> Cenario:
    """Com `parametros`, grava uma versão da política padrão com eles por cima."""
    cenario = Cenario(
        erp=erp or montar_erp(),
        politicas=InMemoryPoliticaCompraRepositorio(),
        avisos=InMemoryAvisosRepositorio(),
        decisoes=InMemoryDecisoesRepositorio(),
        cobrancas=InMemoryCobrancasRepositorio(),
        episodios=InMemoryEpisodiosRepositorio(),
        usuarios=InMemoryUsuariosRepositorio(),
        verificacoes=InMemoryVerificacoesRepositorio(),
        relogio=RelogioFake(AGORA),
    )
    if parametros:
        cenario.politicas.salvar_nova_versao(PARAMETROS_V1.model_copy(update=parametros))
    app.dependency_overrides[get_erp_adapter] = lambda: cenario.erp
    app.dependency_overrides[get_politica_compra_repositorio] = lambda: cenario.politicas
    app.dependency_overrides[get_avisos_repositorio] = lambda: cenario.avisos
    app.dependency_overrides[get_decisoes_repositorio] = lambda: cenario.decisoes
    app.dependency_overrides[get_cobrancas_repositorio] = lambda: cenario.cobrancas
    app.dependency_overrides[get_relogio] = lambda: cenario.relogio
    app.dependency_overrides[get_episodios_repositorio] = lambda: cenario.episodios
    app.dependency_overrides[get_usuarios_repositorio] = lambda: cenario.usuarios
    app.dependency_overrides[get_relogio_das_notificacoes] = lambda: cenario.relogio
    app.dependency_overrides[get_relogio_da_reposicao] = lambda: cenario.relogio
    app.dependency_overrides[get_verificacoes_repositorio] = lambda: cenario.verificacoes
    return cenario


def atrasar(
    cenario: Cenario,
    fornecedor: Fornecedor,
    *itens: tuple[SKU, int],
    prevista: date | None = ONTEM,
    status: StatusPedidoCompra = "enviado",
    key: str = "atrasado",
    recebida: int = 0,
) -> PedidoCompra:
    pedido = make_pedido_compra(fornecedor, status, key=key, data_prevista_entrega=prevista)
    cenario.erp.pedidos_compra.append(pedido)
    cenario.erp.itens_pedido_compra.extend(
        make_item_pedido_compra(pedido, sku, quantidade=quantidade, quantidade_recebida=recebida)
        for sku, quantidade in itens
    )
    return pedido


def painel(client: TestClient) -> dict:
    response = client.get("/painel")
    assert response.status_code == 200
    return response.json()


def codigos(itens: list[dict]) -> list[str]:
    return [i["sku_code"] for i in itens]


def avisar(client: TestClient, sku: SKU, tipo: str = "acabou", **campos: str) -> dict:
    response = client.post(
        "/avisos", json={"sku_code": sku.sku_code, "tipo": tipo, **campos}
    )
    assert response.status_code == 201, response.text
    return response.json()


def decidir(client: TestClient, sku: SKU, tipo: str = "negociando", **campos: object) -> dict:
    response = client.post(
        f"/skus/{sku.sku_code}/decisoes", json={"tipo": tipo, **campos}
    )
    assert response.status_code == 201, response.text
    return response.json()
