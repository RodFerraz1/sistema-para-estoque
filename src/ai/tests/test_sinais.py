"""Testes de `SinaisCorpus` com `FakeEmbedder`, `InMemoryTrechosRepositorio` e `InMemoryDecisionModel`."""
from __future__ import annotations

from collections.abc import Sequence

import pytest

from src.ai.busca import BuscaContexto
from src.ai.decisao import DecisaoIndisponivel
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel, Probabilidades
from src.ai.schemas import AvaliacaoSinais, AvaliacaoTrecho, ProdutoDoSinal, Trecho
from src.ai.sinais import K_SINAIS, LIMIARES_SINAIS, MAX_TRECHOS_SINAIS, SinaisCorpus
from src.catalog.schemas import SKU
from src.purchasing.schemas import MotivoSemCompra, SugestaoPedido
from tests.fakes import make_fornecedor, make_fornecedor_sku, make_sku, make_trecho, repositorio_com

ACEITO: Probabilidades = {"relevante": 0.9, "tem_evidencia": 0.9}
TOALHA = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", categoria="felpudo")


class DecisaoEspia(InMemoryDecisionModel):
    """Guarda os argumentos de cada chamada a `avaliar_trechos` e `avaliar_sinais`."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.buscas: list[tuple[str, list[str]]] = []
        self.chamadas_sinais: list[tuple[str, ProdutoDoSinal, list[str]]] = []

    def avaliar_trechos(self, pergunta: str, trechos: Sequence[Trecho]) -> list[AvaliacaoTrecho]:
        self.buscas.append((pergunta, [t.id for t in trechos]))
        return super().avaliar_trechos(pergunta, trechos)

    def avaliar_sinais(
        self, fornecedor: str, produto: ProdutoDoSinal, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoSinais]:
        self.chamadas_sinais.append((fornecedor, produto, [t.id for t in trechos]))
        return super().avaliar_sinais(fornecedor, produto, trechos)


def sinais_corpus(trechos: list[Trecho], decisao: InMemoryDecisionModel) -> SinaisCorpus:
    embedder = FakeEmbedder()
    return SinaisCorpus(BuscaContexto(embedder, repositorio_com(trechos, embedder), decisao), decisao)


def sugestao(sku: SKU, fornecedor: str | None = "Katrina Têxtil") -> SugestaoPedido:
    return SugestaoPedido(
        sku_code=sku.sku_code,
        quantidade=120 if fornecedor else 0,
        motivo=None if fornecedor else MotivoSemCompra.SEM_FORNECEDOR,
        fornecedor=make_fornecedor_sku(make_fornecedor(fornecedor)) if fornecedor else None,
        valor_estimado_centavos=0,
        calculo=None,
        alertas=[],
        politica_versao=1,
    )


def test_sinal_acima_do_limiar_vira_sinal_com_mensagem_trechos_e_probabilidade() -> None:
    decisao = InMemoryDecisionModel(
        padrao=ACEITO, sinais={"revisao.md#katrina": {"atraso_do_fornecedor": 0.93}}
    )

    [sinal] = sinais_corpus([make_trecho("revisao.md#katrina")], decisao).para_sugestao(sugestao(TOALHA), TOALHA)

    assert sinal.tipo == "atraso_do_fornecedor"
    assert sinal.mensagem == "Os documentos relatam atraso de entrega da Katrina Têxtil."
    assert sinal.trechos == ["revisao.md#katrina"]
    assert sinal.probabilidade == 0.93


def test_mensagens_de_venda_por_epoca_e_encalhe_citam_o_produto() -> None:
    decisao = InMemoryDecisionModel(padrao=ACEITO, sinais_padrao={"demanda_sazonal": 0.99, "encalhe": 0.99})

    sinais = sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(sugestao(TOALHA), TOALHA)

    assert [(s.tipo, s.mensagem) for s in sinais] == [
        ("demanda_sazonal", "Os documentos relatam venda forte de Toalha Banho Conforto em alguma época do ano."),
        (
            "encalhe",
            "Os documentos relatam encalhe de Toalha Banho Conforto ou da categoria dele numa compra anterior.",
        ),
    ]


@pytest.mark.parametrize("tipo", ["atraso_do_fornecedor", "demanda_sazonal", "encalhe"])
def test_probabilidade_exatamente_no_limiar_nao_vira_sinal(tipo: str) -> None:
    limiar = getattr(LIMIARES_SINAIS, tipo)
    decisao = InMemoryDecisionModel(padrao=ACEITO, sinais_padrao={tipo: limiar})  # type: ignore[misc]

    assert sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(sugestao(TOALHA), TOALHA) == []


def test_trechos_do_sinal_vem_do_mais_provavel_ao_menos_provavel_e_so_acima_do_limiar() -> None:
    trechos = [
        make_trecho("a.md#s", "Katrina atrasou"),
        make_trecho("b.md#s", "Katrina atrasou de novo"),
        make_trecho("c.md#s", "Katrina atrasou de novo no Natal"),
    ]
    decisao = InMemoryDecisionModel(
        padrao=ACEITO,
        sinais={
            "a.md#s": {"atraso_do_fornecedor": 0.95},
            "b.md#s": {"atraso_do_fornecedor": 0.2},
            "c.md#s": {"atraso_do_fornecedor": 0.99},
        },
    )

    [sinal] = sinais_corpus(trechos, decisao).para_sugestao(sugestao(TOALHA), TOALHA)

    assert sinal.trechos == ["c.md#s", "a.md#s"]
    assert sinal.probabilidade == 0.99


def test_sinais_nunca_mudam_a_sugestao() -> None:
    original = sugestao(TOALHA)
    decisao = InMemoryDecisionModel(padrao=ACEITO, sinais_padrao={"encalhe": 0.99})

    sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(original, TOALHA)

    assert original == sugestao(TOALHA)


def test_busca_focada_pergunta_pelo_fornecedor_e_pelo_produto_com_k_sinais() -> None:
    trechos = [make_trecho(f"doc{i}.md#s", f"Katrina toalha {i}") for i in range(K_SINAIS + 5)]
    decisao = DecisaoEspia(padrao=ACEITO)

    sinais_corpus(trechos, decisao).para_sugestao(sugestao(TOALHA), TOALHA)

    [(consulta, avaliados)] = decisao.buscas
    assert consulta == (
        "Katrina Têxtil e Toalha Banho Conforto: atrasos de entrega, vendas por época do ano e estoque encalhado"
    )
    assert len(avaliados) == K_SINAIS


def test_so_aceitos_e_conflitantes_vao_aos_sinais_ate_o_maximo_por_similaridade() -> None:
    parecidos = [
        make_trecho(f"doc{i}.md#s", "Katrina Têxtil Toalha Banho Conforto atrasos" + " x" * i) for i in range(12)
    ]
    injecao = make_trecho("ata.md#s", "Katrina Têxtil Toalha Banho Conforto atrasos")
    conflitante = make_trecho(
        "revisao.md#s",
        "Katrina Têxtil e Toalha Banho Conforto: atrasos de entrega, vendas por época do ano e estoque encalhado",
    )
    decisao = DecisaoEspia(
        padrao=ACEITO,
        avaliacoes={
            "ata.md#s": {**ACEITO, "tenta_instruir": 0.95},
            "revisao.md#s": {"contradiz_premissa": 0.95},
            "doc11.md#s": {"relevante": 0.1},
        },
    )

    sinais_corpus([*parecidos, injecao, conflitante], decisao).para_sugestao(sugestao(TOALHA), TOALHA)

    [(fornecedor, produto, avaliados)] = decisao.chamadas_sinais
    assert (fornecedor, produto) == ("Katrina Têxtil", ProdutoDoSinal(nome="Toalha Banho Conforto", categoria="felpudo"))
    assert len(avaliados) == MAX_TRECHOS_SINAIS
    assert "ata.md#s" not in avaliados
    assert "doc11.md#s" not in avaliados
    assert avaliados[0] == "revisao.md#s"
    assert avaliados[1:] == [f"doc{i}.md#s" for i in range(9)]


def test_busca_dos_sinais_nao_pergunta_sobre_conflito() -> None:
    trechos = [make_trecho("contrato.md#s", "Katrina toalha"), make_trecho("revisao.md#s", "Katrina toalha atraso")]
    decisao = InMemoryDecisionModel(padrao=ACEITO, falhar_conflitos=True)

    assert sinais_corpus(trechos, decisao).para_sugestao(sugestao(TOALHA), TOALHA) == []


def test_sugestao_sem_fornecedor_nao_tem_sinal_nem_busca() -> None:
    decisao = InMemoryDecisionModel(falhar_trechos=True, falhar_sinais=True)

    assert sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(sugestao(TOALHA, None), TOALHA) == []


def test_sem_trecho_aceito_nao_pergunta_os_sinais() -> None:
    decisao = InMemoryDecisionModel(falhar_sinais=True)

    assert sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(sugestao(TOALHA), TOALHA) == []


def test_jev_indisponivel_nos_sinais_propaga() -> None:
    decisao = InMemoryDecisionModel(padrao=ACEITO, falhar_sinais=True)

    with pytest.raises(DecisaoIndisponivel):
        sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestao(sugestao(TOALHA), TOALHA)


def test_para_sugestoes_calcula_uma_vez_por_par_de_fornecedor_e_produto() -> None:
    outra_toalha = make_sku("TBC-BEGE-70140-02", produto_nome="Toalha Banho Conforto", categoria="felpudo")
    toalha_da_aurora = make_sku("TBC-CINZ-70140-05", produto_nome="Toalha Banho Conforto", categoria="felpudo")
    rosto = make_sku("TRC-BEGE-4880-01", produto_nome="Toalha Rosto Conforto", categoria="felpudo")
    sem_compra = make_sku("TBC-BRAN-70140-03", produto_nome="Toalha Banho Conforto", categoria="felpudo")
    decisao = DecisaoEspia(padrao=ACEITO, sinais_padrao={"atraso_do_fornecedor": 0.99})

    por_sku = sinais_corpus([make_trecho("a.md#s")], decisao).para_sugestoes(
        [
            (sugestao(TOALHA), TOALHA),
            (sugestao(outra_toalha), outra_toalha),
            (sugestao(toalha_da_aurora, "Aurora Home Center"), toalha_da_aurora),
            (sugestao(rosto), rosto),
            (sugestao(sem_compra, None), sem_compra),
        ]
    )

    assert [(f, p.nome) for f, p, _ in decisao.chamadas_sinais] == [
        ("Katrina Têxtil", "Toalha Banho Conforto"),
        ("Aurora Home Center", "Toalha Banho Conforto"),
        ("Katrina Têxtil", "Toalha Rosto Conforto"),
    ]
    assert list(por_sku) == [
        "TBC-BEGE-70140-01",
        "TBC-BEGE-70140-02",
        "TBC-CINZ-70140-05",
        "TRC-BEGE-4880-01",
        "TBC-BRAN-70140-03",
    ]
    assert por_sku["TBC-BEGE-70140-01"] == por_sku["TBC-BEGE-70140-02"]
    assert por_sku["TBC-CINZ-70140-05"][0].mensagem == "Os documentos relatam atraso de entrega da Aurora Home Center."
    assert por_sku["TBC-BRAN-70140-03"] == []
