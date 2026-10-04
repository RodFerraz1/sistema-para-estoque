"""Contrato dos repositórios de usuários, sessões e tentativas de login.

Roda contra as versões em memória e Postgres. O Postgres requer `docker compose up` +
`alembic upgrade head` e é pulado sem banco. Os testes só usam e-mails do domínio
`@contrato.teste`, e a fixture apaga essas linhas no teardown sem tocar nas outras.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.db.engine import get_engine
from src.usuarios.in_memory import (
    InMemorySessoesRepositorio,
    InMemoryTentativasLoginRepositorio,
    InMemoryUsuariosRepositorio,
)
from src.usuarios.postgres import (
    PostgresSessoesRepositorio,
    PostgresTentativasLoginRepositorio,
    PostgresUsuariosRepositorio,
)
from src.usuarios.repositorio import (
    EmailJaCadastrado,
    SessoesRepositorio,
    TentativasLoginRepositorio,
    UsuariosRepositorio,
)
from src.usuarios.schemas import Papel, Sessao, Usuario

INICIO = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
DOMINIO = "@contrato.teste"


def _db_disponivel() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM copilot.tentativas_login LIMIT 1"))
        return True
    except Exception:
        return False


_sem_banco = pytest.mark.skipif(
    not _db_disponivel(), reason="Postgres com copilot.usuarios precisa estar disponível"
)


@dataclass
class Repositorios:
    usuarios: UsuariosRepositorio
    sessoes: SessoesRepositorio
    tentativas: TentativasLoginRepositorio


def _apagar_linhas_do_contrato() -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "DELETE FROM copilot.sessoes WHERE usuario_id IN "
                "(SELECT id FROM copilot.usuarios WHERE email LIKE :dominio)"
            ),
            {"dominio": f"%{DOMINIO}"},
        )
        conn.execute(text("DELETE FROM copilot.usuarios WHERE email LIKE :dominio"), {"dominio": f"%{DOMINIO}"})
        conn.execute(text("DELETE FROM copilot.tentativas_login WHERE email LIKE :dominio"), {"dominio": f"%{DOMINIO}"})


@pytest.fixture
def postgres() -> Iterator[Repositorios]:
    engine = get_engine()
    try:
        yield Repositorios(
            PostgresUsuariosRepositorio(engine),
            PostgresSessoesRepositorio(engine),
            PostgresTentativasLoginRepositorio(engine),
        )
    finally:
        _apagar_linhas_do_contrato()


@pytest.fixture(params=["memoria", pytest.param("postgres", marks=_sem_banco)])
def repos(request: pytest.FixtureRequest) -> Repositorios:
    if request.param == "memoria":
        return Repositorios(
            InMemoryUsuariosRepositorio(), InMemorySessoesRepositorio(), InMemoryTentativasLoginRepositorio()
        )
    return request.getfixturevalue("postgres")


def usuario(nome: str = "joana", *, papeis: list[Papel] | None = None) -> Usuario:
    return Usuario(
        id=uuid4(),
        nome=nome.title(),
        email=f"{nome}-{uuid4().hex[:8]}{DOMINIO}",
        senha_hash="$argon2id$falso",
        papeis=papeis or ["vendas"],
        ativo=True,
        criado_em=INICIO,
        ultimo_acesso_em=None,
    )


def sessao(dono: Usuario, *, expira_em: datetime | None = None) -> Sessao:
    return Sessao(
        token_hash=uuid4().hex,
        usuario_id=dono.id,
        criada_em=INICIO,
        expira_em=expira_em or INICIO + timedelta(days=30),
        revogada_em=None,
    )


def test_gravar_e_ler_pelo_id_e_pelo_email(repos: Repositorios) -> None:
    gravado = usuario(papeis=["vendas", "reposicao"])
    repos.usuarios.gravar(gravado)

    assert repos.usuarios.por_id(gravado.id) == gravado
    assert repos.usuarios.por_email(gravado.email) == gravado
    assert repos.usuarios.por_email(f"ninguem{DOMINIO}") is None
    assert repos.usuarios.por_id(uuid4()) is None


def test_email_repetido_nao_grava(repos: Repositorios) -> None:
    primeiro = usuario()
    repos.usuarios.gravar(primeiro)
    outro = usuario("bia").model_copy(update={"email": primeiro.email})

    with pytest.raises(EmailJaCadastrado):
        repos.usuarios.gravar(outro)

    assert repos.usuarios.por_email(primeiro.email) == primeiro


def test_registrar_acesso_guarda_o_ultimo(repos: Repositorios) -> None:
    gravado = usuario()
    repos.usuarios.gravar(gravado)

    repos.usuarios.registrar_acesso(gravado.id, INICIO + timedelta(hours=2))

    lido = repos.usuarios.por_id(gravado.id)
    assert lido is not None and lido.ultimo_acesso_em == INICIO + timedelta(hours=2)


def test_sessao_gravada_volta_igual_e_renova(repos: Repositorios) -> None:
    dono = usuario()
    repos.usuarios.gravar(dono)
    gravada = sessao(dono)
    repos.sessoes.gravar(gravada)

    assert repos.sessoes.por_token_hash(gravada.token_hash) == gravada
    assert repos.sessoes.por_token_hash("outro") is None

    repos.sessoes.renovar(gravada.token_hash, INICIO + timedelta(days=40))

    assert repos.sessoes.por_token_hash(gravada.token_hash) == gravada.model_copy(
        update={"expira_em": INICIO + timedelta(days=40)}
    )


def test_revogar_marca_a_hora_uma_vez_so(repos: Repositorios) -> None:
    dono = usuario()
    repos.usuarios.gravar(dono)
    gravada, outra = sessao(dono), sessao(dono)
    repos.sessoes.gravar(gravada)
    repos.sessoes.gravar(outra)

    repos.sessoes.revogar(gravada.token_hash, INICIO + timedelta(hours=1))
    repos.sessoes.revogar(gravada.token_hash, INICIO + timedelta(hours=5))

    revogada = repos.sessoes.por_token_hash(gravada.token_hash)
    assert revogada is not None and revogada.revogada_em == INICIO + timedelta(hours=1)
    assert repos.sessoes.por_token_hash(outra.token_hash) == outra


def test_falhas_desde_filtra_pelo_email_e_pela_hora(repos: Repositorios) -> None:
    joana, bia = f"joana{DOMINIO}", f"bia{DOMINIO}"
    for minutos in (20, 0, 10):
        repos.tentativas.registrar_falha(joana, INICIO + timedelta(minutes=minutos))
    repos.tentativas.registrar_falha(bia, INICIO + timedelta(minutes=15))

    assert repos.tentativas.falhas_desde(joana, INICIO + timedelta(minutes=5)) == [
        INICIO + timedelta(minutes=10),
        INICIO + timedelta(minutes=20),
    ]
    assert repos.tentativas.falhas_desde(bia, INICIO) == [INICIO + timedelta(minutes=15)]


def test_limpar_apaga_so_as_falhas_do_email(repos: Repositorios) -> None:
    joana, bia = f"joana{DOMINIO}", f"bia{DOMINIO}"
    repos.tentativas.registrar_falha(joana, INICIO)
    repos.tentativas.registrar_falha(bia, INICIO)

    repos.tentativas.limpar(joana)

    assert repos.tentativas.falhas_desde(joana, INICIO) == []
    assert repos.tentativas.falhas_desde(bia, INICIO) == [INICIO]


@_sem_banco
def test_postgres_recusa_email_com_maiuscula_e_papel_desconhecido(postgres: Repositorios) -> None:
    for invalido in (
        usuario().model_copy(update={"email": f"Joana{DOMINIO}"}),
        usuario().model_copy(update={"papeis": ["gerente"]}),
    ):
        with pytest.raises(IntegrityError):
            postgres.usuarios.gravar(invalido)


def test_listar_vem_pelo_nome(repos: Repositorios) -> None:
    bia, ana, carla = usuario("bia"), usuario("ana"), usuario("carla")
    for u in (bia, ana, carla):
        repos.usuarios.gravar(u)

    listados = [u for u in repos.usuarios.listar() if u.email.endswith(DOMINIO)]

    assert listados == [ana, bia, carla]


def test_atualizar_troca_papeis_situacao_e_senha(repos: Repositorios) -> None:
    gravado, outro = usuario(), usuario("bia")
    repos.usuarios.gravar(gravado)
    repos.usuarios.gravar(outro)
    mudado = gravado.model_copy(
        update={"papeis": ["comprador", "admin"], "ativo": False, "senha_hash": "$argon2id$nova"}
    )

    repos.usuarios.atualizar(mudado)

    assert repos.usuarios.por_id(gravado.id) == mudado
    assert repos.usuarios.por_id(outro.id) == outro


def test_revogar_do_usuario_fecha_so_as_abertas_dele(repos: Repositorios) -> None:
    dono, outro = usuario(), usuario("bia")
    repos.usuarios.gravar(dono)
    repos.usuarios.gravar(outro)
    ja_revogada, aberta, do_outro = sessao(dono), sessao(dono), sessao(outro)
    for s in (ja_revogada, aberta, do_outro):
        repos.sessoes.gravar(s)
    repos.sessoes.revogar(ja_revogada.token_hash, INICIO + timedelta(hours=1))

    repos.sessoes.revogar_do_usuario(dono.id, INICIO + timedelta(hours=3))

    revogada = repos.sessoes.por_token_hash(ja_revogada.token_hash)
    assert revogada is not None and revogada.revogada_em == INICIO + timedelta(hours=1)
    fechada = repos.sessoes.por_token_hash(aberta.token_hash)
    assert fechada is not None and fechada.revogada_em == INICIO + timedelta(hours=3)
    assert repos.sessoes.por_token_hash(do_outro.token_hash) == do_outro
