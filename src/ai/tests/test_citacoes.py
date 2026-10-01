"""Testes da extração, do veredito e da marcação de citações (funções puras) e da
verificação com o `InMemoryDecisionModel`."""
from __future__ import annotations

from collections.abc import Sequence

import pytest

from src.ai.citacoes import (
    LIMIAR_CITACAO,
    conferir_citacoes,
    decidir_vereditos,
    extrair_citacoes,
    marcar_citacoes,
    veredito,
)
from src.ai.in_memory import InMemoryDecisionModel
from src.ai.schemas import (
    AvaliacaoCitacao,
    Citacao,
    Relacao,
    Trecho,
    Veredito,
    VerificacaoCitacao,
)
from tests.fakes import make_relacao, make_trecho

PRAZOS = "contratos/contrato-katrina-2025.md#clausulas-comerciais/3-prazos"
LEAD_TIME = "fornecedores/katrina-textil.md#lead-time"
VERDELA = "fornecedores/verdela-home.md#lead-time"


def pares(texto: str) -> list[tuple[str, str]]:
    return [(c.trecho_id, c.afirmacao) for c in extrair_citacoes(texto)]


def test_texto_sem_citacao_nao_tem_citacao() -> None:
    assert extrair_citacoes("A Katrina atrasa. A Verdela cumpre o prazo.") == []


def test_citacao_no_fim_da_frase_leva_a_frase_sem_o_colchete() -> None:
    assert extrair_citacoes(f"A Katrina atrasa [{LEAD_TIME}].") == [
        Citacao(trecho_id=LEAD_TIME, afirmacao="A Katrina atrasa.")
    ]


def test_citacao_no_meio_da_frase_leva_a_frase_inteira() -> None:
    assert pares(f"O contrato exige 45 dias [{PRAZOS}] de antecedência.") == [
        (PRAZOS, "O contrato exige 45 dias de antecedência.")
    ]


def test_duas_citacoes_na_mesma_frase_levam_a_mesma_afirmacao() -> None:
    texto = f"O contrato exige 45 dias [{PRAZOS}], mas o observado fica entre 55 e 65 [{LEAD_TIME}]."

    assert pares(texto) == [
        (PRAZOS, "O contrato exige 45 dias, mas o observado fica entre 55 e 65."),
        (LEAD_TIME, "O contrato exige 45 dias, mas o observado fica entre 55 e 65."),
    ]


def test_cada_frase_leva_as_proprias_citacoes() -> None:
    texto = f"Não. A Katrina atrasa [{LEAD_TIME}]. A Verdela cumpre o prazo [{VERDELA}]! Algo mais?"

    assert pares(texto) == [(LEAD_TIME, "A Katrina atrasa."), (VERDELA, "A Verdela cumpre o prazo!")]


@pytest.mark.parametrize(
    "texto",
    [
        f"A Katrina atrasa. [{LEAD_TIME}] A Verdela cumpre.",
        f"A Katrina atrasa.[{LEAD_TIME}] A Verdela cumpre.",
        f"A Katrina atrasa.\n[{LEAD_TIME}]\nA Verdela cumpre.",
    ],
)
def test_citacao_depois_do_ponto_fica_com_a_frase_anterior(texto: str) -> None:
    assert pares(texto) == [(LEAD_TIME, "A Katrina atrasa.")]


def test_ponto_de_numero_e_de_caminho_nao_termina_a_frase() -> None:
    texto = f"Cobertura de 1.3 meses, R$ 1.234,56 e o trecho {LEAD_TIME} [{LEAD_TIME}]."

    assert pares(texto) == [(LEAD_TIME, f"Cobertura de 1.3 meses, R$ 1.234,56 e o trecho {LEAD_TIME}.")]


def test_item_de_lista_e_uma_frase_sem_o_marcador() -> None:
    texto = (
        "Pontos:\n"
        f"- **Lead time**: 62 dias [{LEAD_TIME}]\n"
        f"* A Verdela cumpre o prazo [{VERDELA}]\n"
        f"1. Antecedência de 45 dias [{PRAZOS}]"
    )

    assert pares(texto) == [
        (LEAD_TIME, "Lead time: 62 dias"),
        (VERDELA, "A Verdela cumpre o prazo"),
        (PRAZOS, "Antecedência de 45 dias"),
    ]


@pytest.mark.parametrize(
    "colchete",
    [
        "[SKU/TBC-BEGE-70140-01]",
        "[SKU/TBC-BEGE-70140-01#estoque]",
        "[Política de compra ativa (v1)]",
        "[ TBC-AZUL-70140-07 ]",
        "[fornecedores/katrina-textil.md]",
        "[a Katrina](https://katrina.com.br)",
    ],
)
def test_colchete_que_nao_e_id_de_trecho_fica_fora(colchete: str) -> None:
    assert extrair_citacoes(f"O estoque é de 180 unidades {colchete}.") == []


@pytest.mark.parametrize("separador", ["; ", ";", ", ", ","])
def test_colchete_com_varios_ids_vira_uma_citacao_por_id(separador: str) -> None:
    assert pares(f"A Katrina atrasa [{PRAZOS}{separador}{LEAD_TIME}].") == [
        (PRAZOS, "A Katrina atrasa."),
        (LEAD_TIME, "A Katrina atrasa."),
    ]


def test_colchete_misto_so_conta_os_ids_de_trecho() -> None:
    assert pares(f"A Katrina atrasa [{LEAD_TIME}; ficha do SKU].") == [(LEAD_TIME, "A Katrina atrasa.")]


def test_colchetes_lenticulares_espacos_e_crases_sao_citacao() -> None:
    texto = f"A Verdela cumpre o prazo【{VERDELA}】. A Katrina atrasa [ `{LEAD_TIME}` ]."

    assert pares(texto) == [(VERDELA, "A Verdela cumpre o prazo."), (LEAD_TIME, "A Katrina atrasa.")]


def test_hifen_nao_separavel_vira_hifen_no_id_e_na_afirmacao() -> None:
    texto = "O lead‑time do TBC‑BEGE é longo [fornecedores/katrina‑textil.md#lead‑time]."

    assert pares(texto) == [(LEAD_TIME, "O lead-time do TBC-BEGE é longo.")]


def test_id_com_sufixo_de_parte() -> None:
    assert pares("O Veraneio encalhou [reunioes/veraneio.md#sequencia-dos-fatos~2].") == [
        ("reunioes/veraneio.md#sequencia-dos-fatos~2", "O Veraneio encalhou.")
    ]


def test_afirmacao_sem_parenteses_vazios_negrito_nem_espaco_antes_da_pontuacao() -> None:
    texto = f"O teto é de **3 meses de giro** ([{PRAZOS}]), porém há exceção."

    assert pares(texto) == [(PRAZOS, "O teto é de 3 meses de giro, porém há exceção.")]


def test_mesma_citacao_repetida_na_frase_conta_uma_vez() -> None:
    assert pares(f"A Katrina [{LEAD_TIME}] atrasa [{LEAD_TIME}].") == [(LEAD_TIME, "A Katrina atrasa.")]


def test_citacao_sozinha_no_comeco_do_texto_tem_afirmacao_vazia() -> None:
    assert pares(f"[{LEAD_TIME}]\nA Katrina atrasa.") == [(LEAD_TIME, "")]


REDACAO_REAL = (
    "Entendi que você quer uma sugestão de compra. Se não for isso, reformule a pergunta.\n\n"
    "Não. O contrato exige **antecedência mínima de 45 dias** entre o pedido e a data desejada de recebimento "
    f"[{PRAZOS}], mas o lead‑time **real observado** costuma ficar entre **55 e 65 dias** [{LEAD_TIME}]. "
    "Além disso, a Katrina dá prioridade a pedidos feitos **até julho** para entrega em outubro "
    "[fornecedores/katrina-textil.md#sazonalidade-e-capacidade].  \n\n"
    "- **Cobertura atual:** 1,3 meses (≈ 39 dias) [SKU/TBC-BEGE-70140-01]  \n"
    "- **Teto:** 3,0 meses [Política de compra ativa (v1)]\n"
)


def test_redacao_real_de_um_llm() -> None:
    compostas = (
        "Não. O contrato exige antecedência mínima de 45 dias entre o pedido e a data desejada de recebimento, "
        "mas o lead-time real observado costuma ficar entre 55 e 65 dias."
    )
    assert pares(REDACAO_REAL) == [
        (PRAZOS, compostas.removeprefix("Não. ")),
        (LEAD_TIME, compostas.removeprefix("Não. ")),
        (
            "fornecedores/katrina-textil.md#sazonalidade-e-capacidade",
            "Além disso, a Katrina dá prioridade a pedidos feitos até julho para entrega em outubro.",
        ),
    ]


def avaliacao(trecho_id: str, afirmacao: str, escolha: Relacao, confianca: float) -> AvaliacaoCitacao:
    return AvaliacaoCitacao(
        afirmacao=afirmacao,
        trecho_id=trecho_id,
        escolha=escolha,
        confianca=confianca,
        probabilidades={escolha: confianca},
        modelo="jev-1.13.0",
    )


@pytest.mark.parametrize(
    ("escolha", "esperado"),
    [("sustenta", "confirmada"), ("contradiz", "contradita"), ("nao_trata", "sem_suporte")],
)
def test_veredito_segue_a_escolha_com_confianca_no_limiar(escolha: Relacao, esperado: Veredito) -> None:
    assert veredito(avaliacao(LEAD_TIME, "A Katrina atrasa.", escolha, LIMIAR_CITACAO)) == esperado


def test_veredito_abaixo_do_limiar_e_incerta() -> None:
    assert veredito(avaliacao(LEAD_TIME, "A Katrina atrasa.", "sustenta", LIMIAR_CITACAO - 0.01)) == "incerta"
    assert veredito(avaliacao(LEAD_TIME, "A Katrina atrasa.", "sustenta", 0.70), limiar=0.60) == "confirmada"


def test_vereditos_de_cada_citacao_na_ordem_do_texto() -> None:
    citacoes = [
        Citacao(trecho_id="inventado.md#x", afirmacao="A Katrina atrasa."),
        Citacao(trecho_id=LEAD_TIME, afirmacao="A Katrina atrasa."),
        Citacao(trecho_id=VERDELA, afirmacao="A Verdela atrasa."),
        Citacao(trecho_id=PRAZOS, afirmacao="O contrato exige 45 dias."),
    ]
    avaliacoes = [
        avaliacao(VERDELA, "A Verdela atrasa.", "contradiz", 0.97),
        avaliacao(LEAD_TIME, "A Katrina atrasa.", "sustenta", 0.95),
    ]

    verificacoes = decidir_vereditos(citacoes, {LEAD_TIME, VERDELA, PRAZOS}, avaliacoes)

    assert [(v.trecho_id, v.veredito, v.confianca) for v in verificacoes] == [
        ("inventado.md#x", "inventada", None),
        (LEAD_TIME, "confirmada", 0.95),
        (VERDELA, "contradita", 0.97),
        (PRAZOS, "incerta", None),
    ]
    assert verificacoes[0].afirmacao == "A Katrina atrasa."


def verificacao(trecho_id: str, afirmacao: str, resultado: Veredito) -> VerificacaoCitacao:
    return VerificacaoCitacao(trecho_id=trecho_id, afirmacao=afirmacao, veredito=resultado, confianca=None)


@pytest.mark.parametrize(
    ("resultado", "marcado"),
    [
        ("confirmada", f"[{LEAD_TIME}]"),
        ("sem_suporte", f"[{LEAD_TIME} - não confirmada]"),
        ("incerta", f"[{LEAD_TIME} - não confirmada]"),
        ("contradita", f"[{LEAD_TIME} - o trecho diz o contrário]"),
        ("inventada", f"[{LEAD_TIME} - trecho inexistente]"),
    ],
)
def test_marcacao_de_cada_veredito(resultado: Veredito, marcado: str) -> None:
    texto = f"A Katrina atrasa [{LEAD_TIME}]. Fim."

    marcada = marcar_citacoes(texto, [verificacao(LEAD_TIME, "A Katrina atrasa.", resultado)])

    assert marcada == f"A Katrina atrasa {marcado}. Fim."


def test_texto_sem_citacao_volta_igual() -> None:
    texto = "A Katrina atrasa [SKU/TBC-BEGE-70140-01]. Fim."

    assert marcar_citacoes(texto, []) == texto


def test_citacao_sem_verificacao_fica_como_esta() -> None:
    texto = f"A Katrina atrasa【{LEAD_TIME}】."

    assert marcar_citacoes(texto, [verificacao(LEAD_TIME, "Outra frase.", "inventada")]) == texto


def test_mesmo_id_em_frases_diferentes_e_marcado_pela_verificacao_de_cada_frase() -> None:
    texto = f"A Katrina atrasa [{LEAD_TIME}]. A Katrina entrega em 30 dias [{LEAD_TIME}]."

    marcada = marcar_citacoes(
        texto,
        [
            verificacao(LEAD_TIME, "A Katrina atrasa.", "confirmada"),
            verificacao(LEAD_TIME, "A Katrina entrega em 30 dias.", "contradita"),
        ],
    )

    assert marcada == (
        f"A Katrina atrasa [{LEAD_TIME}]. A Katrina entrega em 30 dias [{LEAD_TIME} - o trecho diz o contrário]."
    )


def test_colchete_com_varios_ids_e_reescrito_com_a_marca_de_cada_um() -> None:
    texto = f"A Katrina atrasa【{PRAZOS}, fornecedores/katrina‑textil.md#lead-time】."

    marcada = marcar_citacoes(
        texto,
        [
            verificacao(PRAZOS, "A Katrina atrasa.", "confirmada"),
            verificacao(LEAD_TIME, "A Katrina atrasa.", "inventada"),
        ],
    )

    assert marcada == f"A Katrina atrasa[{PRAZOS}; {LEAD_TIME} - trecho inexistente]."


class DecisaoGravadora(InMemoryDecisionModel):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.pares: list[tuple[str, str]] = []

    def verificar_citacoes(self, pares: Sequence[tuple[str, Trecho]]) -> list[AvaliacaoCitacao]:
        self.pares.extend((afirmacao, trecho.id) for afirmacao, trecho in pares)
        return super().verificar_citacoes(pares)


def test_conferir_pergunta_uma_vez_por_par_e_decide_o_veredito_de_cada_citacao() -> None:
    decisao = DecisaoGravadora(
        citacoes={LEAD_TIME: make_relacao("sustenta", 0.95), VERDELA: make_relacao("contradiz", 0.40)}
    )
    texto = (
        f"A Katrina atrasa [{LEAD_TIME}] e o contrato pede 45 dias [{PRAZOS}]. "
        f"A Verdela atrasa [{VERDELA}; inventado.md#x]."
    )

    conferidas = conferir_citacoes(texto, [make_trecho(LEAD_TIME), make_trecho(VERDELA), make_trecho(PRAZOS)], decisao)

    assert decisao.pares == [
        ("A Katrina atrasa e o contrato pede 45 dias.", LEAD_TIME),
        ("A Katrina atrasa e o contrato pede 45 dias.", PRAZOS),
        ("A Verdela atrasa.", VERDELA),
    ]
    assert [(v.trecho_id, v.veredito) for v in conferidas.verificacoes] == [
        (LEAD_TIME, "confirmada"),
        (PRAZOS, "sem_suporte"),
        (VERDELA, "incerta"),
        ("inventado.md#x", "inventada"),
    ]
    assert conferidas.texto == (
        f"A Katrina atrasa [{LEAD_TIME}] e o contrato pede 45 dias [{PRAZOS} - não confirmada]. "
        f"A Verdela atrasa [{VERDELA} - não confirmada; inventado.md#x - trecho inexistente]."
    )
    assert not conferidas.decisao_indisponivel


def test_conferir_nao_chama_o_modelo_sem_citacao_do_contexto_nem_com_afirmacao_vazia() -> None:
    decisao = InMemoryDecisionModel(falhar_citacoes=True)
    texto = f"[{LEAD_TIME}]\nA Katrina atrasa [inventado.md#x]."

    conferidas = conferir_citacoes(texto, [make_trecho(LEAD_TIME)], decisao)

    assert [(v.trecho_id, v.veredito) for v in conferidas.verificacoes] == [
        (LEAD_TIME, "incerta"),
        ("inventado.md#x", "inventada"),
    ]
    assert not conferidas.decisao_indisponivel


def test_conferir_com_o_modelo_fora_do_ar_deixa_incertas_as_do_contexto_e_avisa_a_queda() -> None:
    decisao = InMemoryDecisionModel(falhar_citacoes=True)
    texto = f"A Katrina atrasa [{LEAD_TIME}]. O prazo é de 45 dias [inventado.md#x]."

    conferidas = conferir_citacoes(texto, [make_trecho(LEAD_TIME)], decisao)

    assert conferidas.decisao_indisponivel
    assert [(v.trecho_id, v.veredito, v.confianca) for v in conferidas.verificacoes] == [
        (LEAD_TIME, "incerta", None),
        ("inventado.md#x", "inventada", None),
    ]
    assert conferidas.texto == (
        f"A Katrina atrasa [{LEAD_TIME} - não confirmada]. O prazo é de 45 dias [inventado.md#x - trecho inexistente]."
    )
