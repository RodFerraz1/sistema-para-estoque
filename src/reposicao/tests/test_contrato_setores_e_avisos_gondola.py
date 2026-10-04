"""Contrato do `SetoresRepositorio` e do `AvisosGondolaRepositorio`.

Roda contra as versões em memória e Postgres. O Postgres requer `docker compose up` +
`alembic upgrade head` e é pulado sem banco. Como `listar` e `dos_skus` olham as tabelas
inteiras, a fixture guarda as linhas existentes de `setores`, `setores_sku` e
`avisos_gondola` em tabelas temporárias, esvazia as tabelas e devolve as linhas no teardown.
Os check constraints são conferidos só no Postgres.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db.engine import get_engine
from src.reposicao.in_memory import InMemoryAvisosGondolaRepositorio, InMemorySetoresRepositorio
from src.reposicao.postgres import PostgresAvisosGondolaRepositorio, PostgresSetoresRepositorio
from src.reposicao.repositorio import AvisosGondolaRepositorio, SetoresRepositorio, SetorJaExiste
from src.reposicao.schemas import AvisoGondola, Setor, SetorDoSku
from tests.autor_no_banco import AUTOR, autor_no_banco

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
SKU = "TAP-MARR-4060-01"
OUTRO_SKU = "TAP-CINZ-4060-02"
TAPETES = Setor(id=UUID("00000000-0000-0000-0000-00000000c001"), nome="Tapetes", ativo=True)
BANHO = Setor(id=UUID("00000000-0000-0000-0000-00000000c002"), nome="Banho", ativo=True)
TABELAS = ("avisos_gondola", "setores_sku", "setores")


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.avisos_gondola LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.avisos_gondola precisa estar disponível"
)


@dataclass
class Repositorios:
    setores: SetoresRepositorio
    avisos: AvisosGondolaRepositorio


@pytest.fixture
def no_postgres() -> Iterator[Repositorios]:
    with autor_no_banco(), get_engine().connect() as conn:
        for tabela in TABELAS:
            conn.execute(text(f"CREATE TEMP TABLE backup_{tabela} AS SELECT * FROM copilot.{tabela}"))
            conn.execute(text(f"DELETE FROM copilot.{tabela}"))
        conn.commit()
        try:
            yield Repositorios(PostgresSetoresRepositorio(get_engine()), PostgresAvisosGondolaRepositorio(get_engine()))
        finally:
            for tabela in TABELAS:
                conn.execute(text(f"DELETE FROM copilot.{tabela}"))
            for tabela in reversed(TABELAS):
                conn.execute(text(f"INSERT INTO copilot.{tabela} SELECT * FROM backup_{tabela}"))
                conn.execute(text(f"DROP TABLE backup_{tabela}"))
            conn.commit()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def repositorios(request: pytest.FixtureRequest) -> Repositorios:
    if request.param == "memoria":
        return Repositorios(InMemorySetoresRepositorio(), InMemoryAvisosGondolaRepositorio())
    return request.getfixturevalue("no_postgres")


@pytest.fixture
def setores(repositorios: Repositorios) -> SetoresRepositorio:
    return repositorios.setores


@pytest.fixture
def avisos(repositorios: Repositorios) -> AvisosGondolaRepositorio:
    for setor in (TAPETES, BANHO):
        repositorios.setores.gravar(setor)
    return repositorios.avisos


def setor_do_sku(sku_code: str = SKU, setor: Setor = TAPETES, *, minutos: int = 0, **campos: Any) -> SetorDoSku:
    return SetorDoSku(
        sku_code=sku_code,
        setor_id=setor.id,
        atualizado_em=INICIO + timedelta(minutes=minutos),
        **({"usuario_id": AUTOR.id} | campos),
    )


def aviso(sku_code: str = SKU, *, minutos: int = 0, id: UUID | None = None, **campos: Any) -> AvisoGondola:
    padrao: dict[str, Any] = {
        "setor_id": TAPETES.id,
        "comentario": None,
        "disponivel_no_erp": 400,
        "avisado_por": AUTOR.nome,
        "usuario_id": AUTOR.id,
    }
    return AvisoGondola(
        id=id or uuid4(), sku_code=sku_code, criado_em=INICIO + timedelta(minutes=minutos), **(padrao | campos)
    )


def test_gravar_e_carregar_devolve_o_setor_igual(setores: SetoresRepositorio) -> None:
    setores.gravar(TAPETES)

    assert setores.carregar(TAPETES.id) == TAPETES
    assert setores.carregar(uuid4()) is None


def test_listar_traz_todos_pelo_nome(setores: SetoresRepositorio) -> None:
    inativo = Setor(id=uuid4(), nome="Cozinha", ativo=False)
    for setor in (TAPETES, inativo, BANHO):
        setores.gravar(setor)

    assert setores.listar() == [BANHO, inativo, TAPETES]


def test_gravar_com_o_mesmo_id_renomeia_e_desativa(setores: SetoresRepositorio) -> None:
    setores.gravar(TAPETES)
    renomeado = TAPETES.model_copy(update={"nome": "Tapetes e capachos", "ativo": False})

    setores.gravar(renomeado)

    assert setores.listar() == [renomeado]


def test_nome_repetido_sem_diferenciar_maiusculas_nao_grava(setores: SetoresRepositorio) -> None:
    setores.gravar(TAPETES)
    setores.gravar(BANHO)

    with pytest.raises(SetorJaExiste):
        setores.gravar(Setor(id=uuid4(), nome="tapetes", ativo=True))
    with pytest.raises(SetorJaExiste):
        setores.gravar(BANHO.model_copy(update={"nome": "TAPETES"}))
    assert setores.listar() == [BANHO, TAPETES]


def test_lembrar_guarda_o_setor_do_sku_e_troca_o_anterior(setores: SetoresRepositorio) -> None:
    setores.gravar(TAPETES)
    setores.gravar(BANHO)
    primeiro, corrigido = setor_do_sku(setor=BANHO), setor_do_sku(setor=TAPETES, minutos=10)
    do_outro = setor_do_sku(OUTRO_SKU, usuario_id=None)

    setores.lembrar(primeiro)
    setores.lembrar(do_outro)
    setores.lembrar(corrigido)

    assert setores.do_sku(SKU) == corrigido
    assert setores.do_sku("NAO-EXISTE") is None
    assert setores.dos_skus() == {SKU: corrigido, OUTRO_SKU: do_outro}


def test_sem_setor_conhecido_dos_skus_e_vazio(setores: SetoresRepositorio) -> None:
    assert setores.dos_skus() == {}


def test_gravar_e_listar_devolve_o_aviso_igual(avisos: AvisosGondolaRepositorio) -> None:
    gravados = [
        aviso(),
        aviso(minutos=1, setor_id=BANHO.id, comentario="Só sobrou o P.", disponivel_no_erp=0),
    ]
    for a in gravados:
        avisos.gravar(a)

    assert avisos.listar() == list(reversed(gravados))


def test_listar_filtra_pelo_sku(avisos: AvisosGondolaRepositorio) -> None:
    do_sku, do_outro = aviso(SKU), aviso(OUTRO_SKU, minutos=1)
    avisos.gravar(do_sku)
    avisos.gravar(do_outro)

    assert avisos.listar(SKU) == [do_sku]
    assert avisos.listar() == [do_outro, do_sku]
    assert avisos.listar("NAO-EXISTE") == []


def test_mesma_hora_desempata_pelo_id(avisos: AvisosGondolaRepositorio) -> None:
    menor = aviso(id=UUID("00000000-0000-0000-0000-000000000001"))
    maior = aviso(id=UUID("ffffffff-0000-0000-0000-000000000000"))
    avisos.gravar(menor)
    avisos.gravar(maior)

    assert avisos.listar() == [maior, menor]


def test_do_usuario_traz_os_dele_a_partir_da_data(avisos: AvisosGondolaRepositorio) -> None:
    antigo, no_limite, recente = aviso(minutos=-1), aviso(minutos=0), aviso(OUTRO_SKU, minutos=5)
    for a in (recente, antigo, no_limite):
        avisos.gravar(a)

    assert avisos.do_usuario(AUTOR.id, INICIO) == [recente, no_limite]
    assert avisos.do_usuario(uuid4(), INICIO - timedelta(days=1)) == []


@_sem_banco
def test_nome_do_setor_nao_pode_ser_vazio(no_postgres: Repositorios) -> None:
    with pytest.raises(IntegrityError):
        no_postgres.setores.gravar(Setor(id=uuid4(), nome=" ", ativo=True))


@_sem_banco
def test_nome_de_quem_avisou_nao_pode_ser_vazio(no_postgres: Repositorios) -> None:
    no_postgres.setores.gravar(TAPETES)
    with pytest.raises(IntegrityError):
        no_postgres.avisos.gravar(aviso(avisado_por=" "))
