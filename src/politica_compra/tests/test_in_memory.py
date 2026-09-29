"""Versionamento da política pelo `InMemoryPoliticaCompraRepositorio`."""
from __future__ import annotations

from datetime import UTC, datetime

from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.politica_compra.schemas import CriterioFornecedor, PARAMETROS_V1


NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def test_nasce_com_a_v1_padrao() -> None:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)

    ativa = repo.ativa()

    assert ativa.versao == 1
    assert ativa.parametros.teto_meses == 3.0
    assert ativa.parametros.piso_alerta_dias == 20
    assert ativa.parametros.piso_reposicao_dias == 30
    assert ativa.parametros.dias_historico_minimo == 60


def test_salvar_nova_versao_incrementa_e_vira_ativa() -> None:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)
    novos = PARAMETROS_V1.model_copy(
        update={"criterio_fornecedor": CriterioFornecedor.MENOR_LEAD_TIME}
    )

    salva = repo.salvar_nova_versao(novos)

    assert salva.versao == 2
    assert salva.criada_em == NOW
    assert salva.parametros == novos
    assert repo.ativa() == salva


def test_versao_inexistente_devolve_none() -> None:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)

    assert repo.versao(2) is None


def test_versoes_antigas_continuam_gravadas() -> None:
    repo = InMemoryPoliticaCompraRepositorio(now=NOW)
    v1 = repo.ativa()

    repo.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"teto_meses": 4.0}))
    repo.salvar_nova_versao(PARAMETROS_V1.model_copy(update={"teto_meses": 5.0}))

    assert repo.versao(1) == v1
    assert repo.versao(2) is not None
    assert repo.ativa().parametros.teto_meses == 5.0
