"""Contas do relatório do registro de decisão, com registros em memória."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from scripts.relatorio_registros import (
    Duracao,
    ResumoConfianca,
    confianca_por_intencao,
    duracoes_por_acao,
    normalizar_pergunta,
    percentil,
    perguntas_para_exportar,
    perto_do_limiar,
    relatorio,
    repetidas,
    sinais_por_tipo,
    sugestoes_sem_sinais,
    vereditos,
)
from src.ai.schemas import RegistroDecisao, SinaisDoSKU, SinalCorpus, VerificacaoCitacao
from tests.fakes import make_entendimento

INICIO = datetime(2026, 9, 30, 19, 0, tzinfo=UTC)
LEAD_TIME = "Qual o lead time de verdade da Katrina?"


def registro(
    minutos: int,
    pergunta: str,
    intencao: str = "situacao_sku",
    confianca: float = 1.0,
    acao: str = "respondeu",
    duracao_ms: int = 1000,
    **campos: object,
) -> RegistroDecisao:
    return RegistroDecisao.model_validate(
        {
            "id": uuid4(),
            "criado_em": INICIO + timedelta(minutes=minutos),
            "pergunta": pergunta,
            "intencao": intencao,
            "confianca": confianca,
            "faixa": "alta" if confianca >= 0.8 else "media" if confianca >= 0.5 else "baixa",
            "acao": acao,
            "skus": [],
            "entendimento": make_entendimento(intencao, confianca),
            "trechos": [],
            "redator": None,
            "resposta": "texto",
            "duracao_ms": duracao_ms,
            "sinais": [],
            "citacoes": [],
            **campos,
        }
    )


def citacao(veredito: str, confianca: float | None) -> VerificacaoCitacao:
    return VerificacaoCitacao(trecho_id="a.md#b", afirmacao="Frase.", veredito=veredito, confianca=confianca)


def sinal(tipo: str) -> SinalCorpus:
    return SinalCorpus(tipo=tipo, mensagem="m", trechos=["a.md#b"], probabilidade=0.9)


REGISTROS = [
    registro(0, LEAD_TIME, confianca=0.33, acao="pediu_esclarecimento", duracao_ms=400),
    registro(1, "qual o lead  time de verdade da katrína? ", confianca=0.45, acao="pediu_esclarecimento", duracao_ms=420),
    registro(2, LEAD_TIME, "politica_ou_fornecedor", 0.52, acao="confirmou_e_respondeu", duracao_ms=5000),
    registro(
        3,
        "Quanto compro do TBC-BEGE-70140-01?",
        "sugestao_compra",
        0.98,
        duracao_ms=4000,
        redator="groq:openai/gpt-oss-120b",
        citacoes=[citacao("confirmada", 0.85), citacao("incerta", 0.75), citacao("inventada", None)],
        sinais=[
            SinaisDoSKU(sku_code="TBC-BEGE-70140-01", sinais=[sinal("atraso_do_fornecedor"), sinal("encalhe")]),
            SinaisDoSKU(sku_code="TBC-BEGE-70140-03", sinais=None),
        ],
    ),
    registro(4, "Vai chover amanhã?", "fora_de_escopo", 1.0, acao="fora_de_escopo", duracao_ms=300),
    registro(
        5,
        "Quanto compro do TBC-BEGE-70140-01?",
        "sugestao_compra",
        0.96,
        duracao_ms=6000,
        redator="sem_llm",
        citacoes=[citacao("contradita", 0.95)],
        sinais=[SinaisDoSKU(sku_code="TBC-BEGE-70140-01", sinais=[sinal("atraso_do_fornecedor")])],
    ),
]


def test_normalizar_tira_acento_caixa_e_espacos_repetidos() -> None:
    assert normalizar_pergunta("  Qual o LEAD   time da Katrína?\n") == "qual o lead time da katrina?"


def test_confianca_por_intencao_resume_minima_mediana_e_maxima() -> None:
    resumo = confianca_por_intencao(REGISTROS)

    assert resumo["situacao_sku"] == ResumoConfianca(2, 0.33, 0.39, 0.45)
    assert resumo["politica_ou_fornecedor"] == ResumoConfianca(1, 0.52, 0.52, 0.52)
    assert resumo["sugestao_compra"] == ResumoConfianca(2, 0.96, 0.97, 0.98)
    assert list(resumo) == ["situacao_sku", "sugestao_compra", "politica_ou_fornecedor", "fora_de_escopo"]


def test_repetidas_juntam_a_pergunta_normalizada_e_ordenam_pela_dispersao() -> None:
    [lead_time, sugestao] = repetidas(REGISTROS)

    assert lead_time.pergunta == LEAD_TIME
    assert lead_time.vezes == 3
    assert lead_time.intencoes == ("situacao_sku", "politica_ou_fornecedor")
    assert (lead_time.minima, lead_time.maxima, lead_time.dispersao) == (0.33, 0.52, 0.19)
    assert (sugestao.vezes, sugestao.dispersao) == (2, 0.02)


def test_duracao_por_acao_tem_mediana_e_p90() -> None:
    duracoes = duracoes_por_acao(REGISTROS)

    assert duracoes["respondeu"] == Duracao(2, 5000, 6000)
    assert duracoes["pediu_esclarecimento"] == Duracao(2, 410, 420)
    assert "confirmou_e_respondeu" in duracoes


def test_percentil_pelo_posto_mais_proximo() -> None:
    valores = list(range(1, 11))

    assert percentil(valores, 90) == 9
    assert percentil(valores, 50) == 5
    assert percentil([7], 90) == 7


def test_vereditos_e_confiancas_perto_do_limiar() -> None:
    assert vereditos(REGISTROS) == {"confirmada": 1, "incerta": 1, "inventada": 1, "contradita": 1}
    assert perto_do_limiar(REGISTROS, 0.80) == (2, 3)


def test_sinais_por_tipo_e_sugestoes_com_sinais_nulos() -> None:
    assert sinais_por_tipo(REGISTROS) == {"atraso_do_fornecedor": 2, "encalhe": 1}
    assert sugestoes_sem_sinais(REGISTROS) == (1, 3)


def test_exportar_traz_as_perguntas_novas_sem_a_resposta_do_jev() -> None:
    exportadas = perguntas_para_exportar(REGISTROS, ["Vai chover amanhã?", "QUAL o lead time de verdade da Katrina?"])

    assert exportadas == [
        {"id": "r01", "pergunta": "Quanto compro do TBC-BEGE-70140-01?", "intencao": None, "produtos_aceitos": None}
    ]


def test_relatorio_mostra_totais_e_secoes() -> None:
    texto = relatorio(REGISTROS)

    assert "Registros: 6, de 2026-09-30 19:00 a 2026-09-30 19:05 (UTC)" in texto
    assert "Perguntas distintas: 3" in texto
    assert "Faixas: alta 3, media 1, baixa 2" in texto
    assert "3x  0.33-0.52  0.19  situacao_sku/politica_ou_fornecedor: " + LEAD_TIME in texto
    assert "sem redação (resposta em código) 4" in texto
    assert "2 de 3 confianças a menos de 0.10 do LIMIAR_CITACAO (0.80)" in texto
    assert "1 de 3 sugestões com sinais nulos" in texto


def test_relatorio_sem_registros() -> None:
    assert relatorio([]) == "Nenhum registro de decisão."
