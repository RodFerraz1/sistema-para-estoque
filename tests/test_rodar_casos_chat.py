"""Contagens da rodada dos casos pelo chat, calculadas sobre respostas de exemplo."""
from __future__ import annotations

import pytest

from scripts.rodar_casos_chat import (
    Contagens,
    RedatorComQuedas,
    colchetes_sem_id,
    quantidades_no_texto,
    sinais_citados,
    somar,
)
from src.ai.redator import RedatorIndisponivel
from src.ai.schemas import SinalCorpus, SugestaoComSinais
from src.purchasing.schemas import SugestaoPedido
from tests.fakes import RedatorGravador

ATRASO = "revisoes/revisao-fornecedores-2026-q1.md#katrina/lead-time"
RISCOS = "revisoes/revisao-fornecedores-2026-q1.md#katrina/riscos"
VERANEIO = "reunioes/2024-07-erro-jogo-veraneio.md#sequencia-dos-fatos"


def sugestao(sku: str, quantidade: int, sinais: list[SinalCorpus] | None = None) -> SugestaoComSinais:
    return SugestaoComSinais(
        sugestao=SugestaoPedido(
            sku_code=sku,
            quantidade=quantidade,
            motivo=None,
            fornecedor=None,
            valor_estimado_centavos=0,
            calculo=None,
            alertas=[],
            politica_versao=1,
        ),
        sinais=sinais,
    )


def sinal(*trechos: str) -> SinalCorpus:
    return SinalCorpus(tipo="atraso_do_fornecedor", mensagem="A Katrina atrasa.", trechos=list(trechos), probabilidade=0.9)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Sem colchete nenhum.", 0),
        (f"A Katrina atrasa [{ATRASO}].", 0),
        (f"A Katrina atrasa 【{ATRASO}】.", 0),
        (f"A Katrina atrasa [{ATRASO} - não confirmada].", 0),
        (f"Duas fontes [{ATRASO}; {RISCOS} - trecho inexistente].", 0),
        ("Estoque de 40 unidades [SKU/TBC-BEGE-70140-01].", 1),
        ("Teto de 3 meses [Política de compra ativa (v1)] e [ TBC-AZUL-70140-07 ].", 2),
        ("Ver 【SKU#alertas】 e [documento.md].", 2),
        (f"Misto [SKU/TBC-BEGE-70140-01, {ATRASO}].", 0),
        (f"Hífen não separável [revisoes/revisao‑fornecedores-2026-q1.md#katrina/lead‑time].", 0),
    ],
)
def test_colchetes_sem_id_de_trecho(texto: str, esperado: int) -> None:
    assert colchetes_sem_id(texto) == esperado


def test_sinais_citados_conta_os_sinais_com_algum_trecho_de_origem_citado() -> None:
    sugestoes = [
        sugestao("TBC-BEGE-70140-01", 120, [sinal(ATRASO, RISCOS), sinal(VERANEIO)]),
        sugestao("TBC-BRAN-70140-02", 0, []),
        sugestao("JDCP-BRAN-QUEEN-02", 30, None),
    ]

    assert sinais_citados(sugestoes, {RISCOS}) == (1, 2)
    assert sinais_citados(sugestoes, set()) == (0, 2)
    assert sinais_citados([], {ATRASO}) == (0, 0)


def test_quantidades_no_texto_procura_o_numero_formatado_como_no_contexto() -> None:
    sugestoes = [sugestao("TBC-BEGE-70140-01", 1234), sugestao("JDCP-BRAN-QUEEN-02", 39), sugestao("CB-OFF--QUEEN-09", 0)]

    assert quantidades_no_texto(sugestoes, "Compre 1.234 unidades do TBC e 0 do CB.") == (2, 3)
    assert quantidades_no_texto(sugestoes, "Compre 1234 unidades, 390 peças, R$ 1,39 e R$ 0,00.") == (0, 3)
    assert quantidades_no_texto(sugestoes, "São 39 unidades.") == (1, 3)
    assert quantidades_no_texto([], "Compre 39.") == (0, 0)


def test_somar_junta_as_contagens_dos_casos() -> None:
    total = somar([Contagens(2, 1, 2, 1, 1), Contagens(0, 0, 1, 2, 3), Contagens()])

    assert total == Contagens(colchetes_sem_id=2, sinais_citados=1, sinais=3, quantidades_no_texto=3, sugestoes=4)


def test_redator_com_quedas_guarda_o_motivo_e_repassa_a_queda() -> None:
    redator = RedatorComQuedas(RedatorGravador(nome="groq:modelo", falhar=True))

    with pytest.raises(RedatorIndisponivel):
        redator.redigir("Pergunta", "Contexto")

    assert redator.queda == "groq:modelo configurado para falhar"
    assert (redator.nome, redator.usa_llm) == ("groq:modelo", True)


def test_redator_com_quedas_sem_queda_devolve_o_texto() -> None:
    redator = RedatorComQuedas(RedatorGravador("Texto."))

    assert redator.redigir("Pergunta", "Contexto") == "Texto."
    assert redator.queda is None
