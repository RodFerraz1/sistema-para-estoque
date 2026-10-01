"""Contrato do `SugestoesFilaRepositorio`.

Roda contra `InMemorySugestoesFilaRepositorioRepositorio` e `PostgresSugestoesFilaRepositorioRepositorio`. O Postgres requer
`docker compose up` + `alembic upgrade head` e é pulado sem banco. Como
`substituir_pendentes` e `listar` olham a tabela inteira, a fixture guarda as
linhas existentes numa tabela temporária, esvazia a tabela e devolve as linhas no
teardown.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import text

from src.ai.schemas import SinalCorpus, SugestaoComSinais
from src.aprovacao.in_memory import InMemorySugestoesFilaRepositorio
from src.aprovacao.postgres import PostgresSugestoesFilaRepositorio
from src.aprovacao.repositorio import SugestoesFilaRepositorio
from src.aprovacao.schemas import SugestaoNaFila
from src.db.engine import get_engine
from src.purchasing.schemas import (
    Alerta,
    FaixaAprovacao,
    LeadTimeOrigem,
    MemoriaCalculo,
    SugestaoPedido,
    TipoAlerta,
)
from tests.fakes import make_fornecedor, make_fornecedor_sku, make_sku

INICIO = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
PEDIDO_COMPRA_ID = uuid4()
FAIXA_1 = FaixaAprovacao(faixa=1, aprovadores="comprador chefe", exige_justificativa=False, ajustes=[])


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.sugestoes_fila LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(),
    reason="Postgres com copilot.sugestoes_fila precisa estar disponível",
)


@pytest.fixture
def postgres() -> Iterator[PostgresSugestoesFilaRepositorio]:
    with get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_fila AS SELECT * FROM copilot.sugestoes_fila"))
        conn.execute(text("DELETE FROM copilot.sugestoes_fila"))
        conn.commit()
        try:
            yield PostgresSugestoesFilaRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.sugestoes_fila"))
            conn.execute(text("INSERT INTO copilot.sugestoes_fila SELECT * FROM backup_fila"))
            conn.execute(text("DROP TABLE backup_fila"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def fila(request: pytest.FixtureRequest) -> SugestoesFilaRepositorio:
    if request.param == "memoria":
        return InMemorySugestoesFilaRepositorio()
    return request.getfixturevalue("postgres")


def na_fila(
    sku_code: str = "TBC-BEGE-70140-01",
    *,
    disponivel: int = 150,
    destaque: bool = False,
    sinais: list[SinalCorpus] | None = None,
    minutos: int = 0,
) -> SugestaoNaFila:
    """Giro de 100 por mês e lead time de 30 dias: a cobertura na chegada sem a compra é
    `(disponivel - 100) / 100`."""
    fornecedor = make_fornecedor_sku(make_fornecedor("Boa Vista Têxtil"), preco_unitario_reais=2000)
    estoque_na_chegada = max(0.0, disponivel - 100.0)
    return SugestaoNaFila(
        id=uuid4(),
        criado_em=INICIO + timedelta(minutes=minutos),
        status="pendente",
        destaque=destaque,
        sku=make_sku(sku_code, produto_nome="Toalha Banho Conforto"),
        sugestao=SugestaoComSinais(
            sugestao=SugestaoPedido(
                sku_code=sku_code,
                quantidade=150,
                motivo=None,
                fornecedor=fornecedor,
                valor_estimado_centavos=300_000,
                calculo=MemoriaCalculo(
                    giro_mensal=100.0,
                    disponivel=disponivel,
                    em_transito=0,
                    posicao=disponivel,
                    lead_time_dias=30,
                    lead_time_origem=LeadTimeOrigem.OBSERVADO,
                    estoque_na_chegada=estoque_na_chegada,
                    qtd_necessaria=150,
                    cobertura_na_chegada_meses=(estoque_na_chegada + 150) / 100,
                ),
                alertas=[Alerta(tipo=TipoAlerta.PERIODO_SAZONAL, mensagem="A compra chega em época forte.")],
                politica_versao=1,
            ),
            sinais=sinais,
        ),
        faixa=FAIXA_1,
    )


def aprovada(s: SugestaoNaFila, minutos: int = 10) -> SugestaoNaFila:
    return s.model_copy(
        update={
            "status": "aprovada",
            "faixa": FaixaAprovacao(
                faixa=2,
                aprovadores="comprador chefe + gerente comercial ou sócio financeiro",
                exige_justificativa=True,
                ajustes=["Viola o teto da política de estoque: sobe da faixa 1 para a 2."],
            ),
            "decidido_em": INICIO + timedelta(minutes=minutos),
            "decidido_por": "Ana",
            "quantidade_aprovada": 400,
            "justificativa": "Compra de oportunidade.",
            "pedido_compra_id": PEDIDO_COMPRA_ID,
        }
    )


def rejeitada(s: SugestaoNaFila, minutos: int = 10) -> SugestaoNaFila:
    return s.model_copy(
        update={
            "status": "rejeitada",
            "decidido_em": INICIO + timedelta(minutes=minutos),
            "decidido_por": "Ana",
            "motivo_rejeicao": "Vamos esperar a feira.",
        }
    )


def test_gravar_e_carregar_devolve_a_sugestao_inteira(fila: SugestoesFilaRepositorio) -> None:
    sinal = SinalCorpus(
        tipo="atraso_do_fornecedor",
        mensagem="Os documentos relatam atraso de entrega da Boa Vista Têxtil.",
        trechos=["reunioes/revisao.md#boa-vista", "contratos/boa-vista.md#prazos"],
        probabilidade=0.97,
    )
    gravada = na_fila(sinais=[sinal], destaque=True)

    assert fila.substituir_pendentes([gravada]) == 0

    assert fila.carregar(gravada.id) == gravada


def test_sinais_nao_calculados_voltam_nulos(fila: SugestoesFilaRepositorio) -> None:
    gravada = na_fila(sinais=None)
    fila.substituir_pendentes([gravada])

    carregada = fila.carregar(gravada.id)

    assert carregada is not None
    assert carregada.sugestao.sinais is None


def test_carregar_inexistente_devolve_nulo(fila: SugestoesFilaRepositorio) -> None:
    assert fila.carregar(uuid4()) is None


def test_substituir_marca_todas_as_pendentes_e_grava_as_novas(fila: SugestoesFilaRepositorio) -> None:
    antigas = [na_fila("A"), na_fila("B")]
    fila.substituir_pendentes(antigas)
    novas = [na_fila("A"), na_fila("C")]

    assert fila.substituir_pendentes(novas) == 2

    assert {s.id for s in fila.listar("pendente")} == {s.id for s in novas}
    assert {s.id for s in fila.listar("substituida")} == {s.id for s in antigas}


def test_substituir_sem_novas_esvazia_a_fila(fila: SugestoesFilaRepositorio) -> None:
    fila.substituir_pendentes([na_fila("A")])

    assert fila.substituir_pendentes([]) == 1

    assert fila.listar("pendente") == []


def test_substituir_nao_mexe_nas_decididas(fila: SugestoesFilaRepositorio) -> None:
    decidida = na_fila("A")
    fila.substituir_pendentes([decidida, na_fila("B")])
    fila.decidir(decidida.id, aprovada)

    assert fila.substituir_pendentes([na_fila("A")]) == 1

    assert fila.carregar(decidida.id) == aprovada(decidida)


def test_pendentes_em_ordem_destaque_primeiro_e_depois_a_mais_urgente(fila: SugestoesFilaRepositorio) -> None:
    folgada = na_fila("A", disponivel=180)
    urgente = na_fila("B", disponivel=110)
    destacada_folgada = na_fila("C", disponivel=190, destaque=True)
    destacada_em_ruptura = na_fila("D", disponivel=50, destaque=True)
    fila.substituir_pendentes([folgada, urgente, destacada_folgada, destacada_em_ruptura])

    assert [s.id for s in fila.listar("pendente")] == [
        destacada_em_ruptura.id,
        destacada_folgada.id,
        urgente.id,
        folgada.id,
    ]


def test_empate_na_fila_desempata_pelo_sku_code(fila: SugestoesFilaRepositorio) -> None:
    segundo = na_fila("TBC-BRAN-70140-01")
    primeiro = na_fila("TBC-BEGE-70140-01")
    fila.substituir_pendentes([segundo, primeiro])

    assert [s.sku_code for s in fila.listar("pendente")] == ["TBC-BEGE-70140-01", "TBC-BRAN-70140-01"]


def test_decidir_aprovacao_grava_a_faixa_e_os_campos_da_decisao(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])

    assert fila.decidir(pendente.id, aprovada) == aprovada(pendente)

    assert fila.carregar(pendente.id) == aprovada(pendente)
    assert fila.listar("pendente") == []
    assert fila.listar("aprovada") == [aprovada(pendente)]


def test_decidir_rejeicao(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])

    fila.decidir(pendente.id, rejeitada)

    assert fila.listar("rejeitada") == [rejeitada(pendente)]


def test_decidir_passa_a_sugestao_como_esta_gravada(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])
    fila.decidir(pendente.id, rejeitada)
    vistas: list[SugestaoNaFila] = []

    fila.decidir(pendente.id, lambda s: vistas.append(s) or s)

    assert vistas == [rejeitada(pendente)]


def test_decidir_so_grava_os_campos_da_decisao(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])

    fila.decidir(pendente.id, lambda s: rejeitada(s).model_copy(update={"destaque": True}))

    assert fila.carregar(pendente.id) == rejeitada(pendente)


def test_decisao_que_falha_nao_grava_nada_e_solta_a_reserva(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])

    def falha(s: SugestaoNaFila) -> SugestaoNaFila:
        raise RuntimeError("ERP fora do ar")

    with pytest.raises(RuntimeError, match="ERP fora do ar"):
        fila.decidir(pendente.id, falha)

    assert fila.carregar(pendente.id) == pendente
    assert fila.decidir(pendente.id, aprovada) == aprovada(pendente)


def test_decidir_inexistente_devolve_nulo_sem_chamar_a_decisao(fila: SugestoesFilaRepositorio) -> None:
    chamadas: list[SugestaoNaFila] = []

    assert fila.decidir(uuid4(), lambda s: chamadas.append(s) or s) is None

    assert chamadas == []


def test_decisao_simultanea_espera_a_primeira_e_ve_a_sugestao_decidida(fila: SugestoesFilaRepositorio) -> None:
    pendente = na_fila()
    fila.substituir_pendentes([pendente])
    primeira_dentro, soltar_primeira = Event(), Event()
    vistas_pela_segunda: list[str] = []

    def primeira(s: SugestaoNaFila) -> SugestaoNaFila:
        primeira_dentro.set()
        assert soltar_primeira.wait(5)
        return aprovada(s)

    def segunda(s: SugestaoNaFila) -> SugestaoNaFila:
        vistas_pela_segunda.append(s.status)
        return s

    def em_paralelo(decisao: Callable[[SugestaoNaFila], SugestaoNaFila]) -> Thread:
        thread = Thread(target=fila.decidir, args=(pendente.id, decisao))
        thread.start()
        return thread

    a = em_paralelo(primeira)
    assert primeira_dentro.wait(5)
    b = em_paralelo(segunda)
    b.join(0.3)
    assert vistas_pela_segunda == []
    soltar_primeira.set()
    a.join(5)
    b.join(5)

    assert vistas_pela_segunda == ["aprovada"]
    assert fila.carregar(pendente.id) == aprovada(pendente)


def test_decididas_da_decisao_mais_recente_para_a_mais_antiga(fila: SugestoesFilaRepositorio) -> None:
    antiga, recente, meio = na_fila("A"), na_fila("B"), na_fila("C")
    fila.substituir_pendentes([antiga, recente, meio])
    for s, minutos in ((antiga, 10), (recente, 30), (meio, 20)):
        fila.decidir(s.id, lambda atual, minutos=minutos: rejeitada(atual, minutos))

    assert [s.id for s in fila.listar("rejeitada")] == [recente.id, meio.id, antiga.id]


def test_substituidas_da_criacao_mais_recente_para_a_mais_antiga(fila: SugestoesFilaRepositorio) -> None:
    antiga, recente = na_fila("A", minutos=0), na_fila("B", minutos=5)
    fila.substituir_pendentes([antiga, recente])
    fila.substituir_pendentes([])

    assert [s.id for s in fila.listar("substituida")] == [recente.id, antiga.id]
