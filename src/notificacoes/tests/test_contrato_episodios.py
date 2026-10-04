"""Contrato do `EpisodiosRepositorio`.

Roda contra `InMemoryEpisodiosRepositorio` e `PostgresEpisodiosRepositorio`. O Postgres
requer `docker compose up` + `alembic upgrade head` e é pulado sem banco. Como a varredura
olha a tabela inteira, a fixture guarda as linhas existentes numa tabela temporária,
esvazia a tabela e devolve as linhas no teardown.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.db.engine import get_engine
from src.notificacoes.in_memory import InMemoryEpisodiosRepositorio
from src.notificacoes.postgres import PostgresEpisodiosRepositorio
from src.notificacoes.repositorio import EpisodiosRepositorio
from src.notificacoes.schemas import Condicao, Episodio

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PEDIDO = UUID("00000000-0000-0000-0000-0000000000a1")
TIPOS_VARRIDOS = ("ruptura", "entrega_atrasada")


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.episodios_alerta LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.episodios_alerta precisa estar disponível"
)


@pytest.fixture
def postgres() -> Iterator[PostgresEpisodiosRepositorio]:
    with get_engine().connect() as conn:
        conn.execute(text("CREATE TEMP TABLE backup_episodios AS SELECT * FROM copilot.episodios_alerta"))
        conn.execute(text("DELETE FROM copilot.episodios_alerta"))
        conn.commit()
        try:
            yield PostgresEpisodiosRepositorio(get_engine())
        finally:
            conn.execute(text("DELETE FROM copilot.episodios_alerta"))
            conn.execute(text("INSERT INTO copilot.episodios_alerta SELECT * FROM backup_episodios"))
            conn.execute(text("DROP TABLE backup_episodios"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def episodios(request: pytest.FixtureRequest) -> EpisodiosRepositorio:
    if request.param == "memoria":
        return InMemoryEpisodiosRepositorio()
    return request.getfixturevalue("postgres")


def ruptura(sku_code: str = "TBC-AZUL-70140-01", **detalhe: object) -> Condicao:
    return Condicao(tipo="ruptura", sku_code=sku_code, papel_destino="comprador", detalhe=detalhe)


def entrega(pedido_id: UUID = PEDIDO) -> Condicao:
    return Condicao(tipo="entrega_atrasada", pedido_id=pedido_id, papel_destino="comprador")


def aviso(minutos: int, sku_code: str = "TBC-AZUL-70140-01") -> Episodio:
    quando = INICIO + timedelta(minutes=minutos)
    return Episodio(
        id=uuid4(),
        tipo="aviso",
        sku_code=sku_code,
        pedido_id=None,
        papel_destino="comprador",
        aberto_em=quando,
        fechado_em=quando,
        detalhe={"tipo": "acabou"},
    )


def depois(minutos: int) -> datetime:
    return INICIO + timedelta(minutes=minutos)


def do_comprador(episodios: EpisodiosRepositorio) -> list[Episodio]:
    return episodios.dos_papeis(["comprador"], limite=100)


def test_varrer_abre_a_condicao_nova_com_o_detalhe_e_varrer_de_novo_nao_duplica(
    episodios: EpisodiosRepositorio,
) -> None:
    episodios.varrer(TIPOS_VARRIDOS, [ruptura(disponivel=0, cobertura_dias=0.0), entrega()], INICIO)
    episodios.varrer(TIPOS_VARRIDOS, [ruptura(disponivel=0, cobertura_dias=0.0), entrega()], depois(5))

    lista = do_comprador(episodios)
    assert sorted((e.tipo, e.aberto_em, e.fechado_em) for e in lista) == [
        ("entrega_atrasada", INICIO, None),
        ("ruptura", INICIO, None),
    ]
    assert next(e for e in lista if e.tipo == "ruptura").detalhe == {"disponivel": 0, "cobertura_dias": 0.0}
    assert next(e for e in lista if e.tipo == "entrega_atrasada").pedido_id == PEDIDO


def test_condicao_que_some_fecha_e_a_que_volta_abre_outro_episodio(episodios: EpisodiosRepositorio) -> None:
    episodios.varrer(TIPOS_VARRIDOS, [ruptura()], INICIO)
    episodios.varrer(TIPOS_VARRIDOS, [], depois(10))
    episodios.varrer(TIPOS_VARRIDOS, [ruptura()], depois(20))

    assert [(e.aberto_em, e.fechado_em) for e in do_comprador(episodios)] == [
        (depois(20), None),
        (INICIO, depois(10)),
    ]


def test_varrer_so_fecha_os_tipos_varridos_e_nao_toca_nos_eventos(episodios: EpisodiosRepositorio) -> None:
    episodios.varrer(["entrega_atrasada"], [entrega()], INICIO)
    episodios.gravar(aviso(1))

    episodios.varrer(["ruptura"], [], depois(10))

    assert sorted((e.tipo, e.fechado_em) for e in do_comprador(episodios)) == [
        ("aviso", depois(1)),
        ("entrega_atrasada", None),
    ]


def test_dos_papeis_filtra_pelo_papel_e_vem_do_mais_recente_com_limite(episodios: EpisodiosRepositorio) -> None:
    episodios.gravar(aviso(1, "A"))
    episodios.gravar(aviso(3, "C"))
    episodios.gravar(aviso(2, "B"))
    episodios.varrer(
        ["queda_de_venda"], [Condicao(tipo="queda_de_venda", sku_code="D", papel_destino="reposicao")], depois(4)
    )

    assert [e.sku_code for e in episodios.dos_papeis(["comprador"], limite=2)] == ["C", "B"]
    assert [e.sku_code for e in episodios.dos_papeis(["reposicao"], limite=10)] == ["D"]
    assert [e.sku_code for e in episodios.dos_papeis(["comprador", "reposicao"], limite=10)] == ["D", "C", "B", "A"]
    assert episodios.dos_papeis(["vendas"], limite=10) == []


def test_abertos_depois_conta_so_os_do_papel_abertos_depois_do_cursor(episodios: EpisodiosRepositorio) -> None:
    episodios.gravar(aviso(1, "A"))
    episodios.gravar(aviso(2, "B"))
    episodios.gravar(aviso(3, "C"))

    assert episodios.abertos_depois(["comprador"], None) == 3
    assert episodios.abertos_depois(["comprador"], depois(2)) == 1
    assert episodios.abertos_depois(["comprador"], depois(3)) == 0
    assert episodios.abertos_depois(["vendas"], None) == 0


@_sem_banco
def test_duas_varreduras_simultaneas_nao_duplicam(postgres: PostgresEpisodiosRepositorio) -> None:
    condicoes = [ruptura(f"SKU-{n:03d}") for n in range(50)] + [entrega()]
    largada = threading.Barrier(2)
    erros: list[BaseException] = []

    def varrer(minutos: int) -> None:
        largada.wait()
        try:
            PostgresEpisodiosRepositorio(get_engine()).varrer(TIPOS_VARRIDOS, condicoes, depois(minutos))
        except BaseException as e:
            erros.append(e)

    threads = [threading.Thread(target=varrer, args=(m,)) for m in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert erros == []
    lista = do_comprador(postgres)
    assert len(lista) == len(condicoes)
    assert all(e.fechado_em is None for e in lista)
