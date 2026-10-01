"""Validação de `ParametrosPolitica`: um caso inválido por regra da spec."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.politica_compra.schemas import (
    CriterioFornecedor,
    LeadTimeBase,
    MotivoDestaque,
    ParametrosPolitica,
    SazonalidadeModo,
)


def _v1(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "teto_meses": 3.0,
        "piso_alerta_dias": 20,
        "piso_reposicao_dias": 30,
        "ciclo_compra_meses": 1.0,
        "lead_time_base": "observado",
        "criterio_fornecedor": "menor_preco",
        "sazonalidade_modo": "alertar",
        "meses_quentes": [5, 6, 11, 12],
        "extra_sazonal_meses": 2.0,
        "dias_historico_minimo": 60,
        "faixa_1_ate_reais": 15_000,
        "faixa_2_ate_reais": 60_000,
        "faixa_3_ate_reais": 150_000,
        "motivos_de_destaque": ["ruptura_antes_da_chegada", "viola_teto"],
    }
    return base | overrides


def test_parametros_v1_validos() -> None:
    p = ParametrosPolitica.model_validate(_v1())

    assert p.teto_meses == 3.0
    assert p.lead_time_base is LeadTimeBase.OBSERVADO
    assert p.criterio_fornecedor is CriterioFornecedor.MENOR_PRECO
    assert p.sazonalidade_modo is SazonalidadeModo.ALERTAR
    assert p.meses_quentes == (5, 6, 11, 12)
    assert (p.faixa_1_ate_reais, p.faixa_2_ate_reais, p.faixa_3_ate_reais) == (
        15_000,
        60_000,
        150_000,
    )
    assert p.motivos_de_destaque == (MotivoDestaque.RUPTURA_ANTES_DA_CHEGADA, MotivoDestaque.VIOLA_TETO)


def test_parametros_sao_imutaveis() -> None:
    p = ParametrosPolitica.model_validate(_v1())

    with pytest.raises(ValidationError):
        p.teto_meses = 4.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("regra", "overrides"),
    [
        ("teto_meses > 0", {"teto_meses": 0}),
        ("ciclo_compra_meses > 0", {"ciclo_compra_meses": 0}),
        ("extra_sazonal_meses >= 0", {"extra_sazonal_meses": -0.5}),
        ("dias_historico_minimo >= 0", {"dias_historico_minimo": -1}),
        ("piso_alerta_dias >= 1", {"piso_alerta_dias": 0}),
        (
            "piso_alerta_dias <= piso_reposicao_dias",
            {"piso_alerta_dias": 31, "piso_reposicao_dias": 30},
        ),
        (
            "piso_reposicao + ciclo <= teto",
            {"piso_reposicao_dias": 60, "ciclo_compra_meses": 1.5, "teto_meses": 3.0},
        ),
        ("meses_quentes sem repetição", {"meses_quentes": [5, 5, 12]}),
        ("faixa_1_ate_reais > 0", {"faixa_1_ate_reais": 0}),
        ("faixa_1 < faixa_2", {"faixa_1_ate_reais": 60_000}),
        ("faixa_2 < faixa_3", {"faixa_2_ate_reais": 150_000}),
        ("faixas em ordem", {"faixa_1_ate_reais": 150_000, "faixa_3_ate_reais": 15_000}),
        ("motivos_de_destaque sem repetição", {"motivos_de_destaque": ["viola_teto", "viola_teto"]}),
        ("motivos_de_destaque fechado", {"motivos_de_destaque": ["estoque_alto"]}),
        ("meses_quentes >= 1", {"meses_quentes": [0, 5]}),
        ("meses_quentes <= 12", {"meses_quentes": [5, 13]}),
        ("lead_time_base fechado", {"lead_time_base": "media"}),
        ("criterio_fornecedor fechado", {"criterio_fornecedor": "melhor_nota"}),
        ("sazonalidade_modo fechado", {"sazonalidade_modo": "ajustar"}),
        ("sem campos extras", {"estoque_seguranca": 10}),
    ],
)
def test_parametros_invalidos_sao_rejeitados(
    regra: str, overrides: dict[str, Any]
) -> None:
    with pytest.raises(ValidationError):
        ParametrosPolitica.model_validate(_v1(**overrides))


def test_campo_obrigatorio_ausente_e_rejeitado() -> None:
    dados = _v1()
    del dados["teto_meses"]

    with pytest.raises(ValidationError):
        ParametrosPolitica.model_validate(dados)


def test_sem_motivo_de_destaque_e_aceito() -> None:
    assert ParametrosPolitica.model_validate(_v1(motivos_de_destaque=[])).motivos_de_destaque == ()


def test_piso_reposicao_mais_ciclo_igual_ao_teto_e_aceito() -> None:
    p = ParametrosPolitica.model_validate(
        _v1(piso_reposicao_dias=60, ciclo_compra_meses=1.0, teto_meses=3.0)
    )

    assert p.piso_reposicao_dias == 60
