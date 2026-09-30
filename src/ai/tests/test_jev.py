"""Testes do `JevDecisionModel` com um cliente TypeSafe falso no lugar da API.

Os testes com o marcador `externo` chamam o Jev real e são pulados sem `JEV_KEY`.
"""
from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import date
from pathlib import Path

import pytest
from typesafe_sdk import Choice, JSONContent, Noul, Question, SystemOneResponse, TypeSafeAPITimeoutError

from src.ai.busca import LIMIARES
from src.ai.corpus import ler_corpus
from src.ai.decisao import DecisaoIndisponivel
from src.ai.identificacao import LIMIAR_PRODUTO, produtos_do_catalogo
from src.ai.jev import PERGUNTAS_SINAIS, JevDecisionModel, criar_cliente
from src.ai.schemas import ProdutoDoSinal, Trecho
from src.ai.sinais import LIMIARES_SINAIS
from src.db.config import get_settings
from tests.fakes import make_sku, make_trecho

RAIZ = Path(__file__).resolve().parents[3]
EVALS = RAIZ / "evals"
SPIKE_R2 = EVALS / "resultados" / "spike-2026-09-30-r2.json"


class ClienteFalso:
    """Responde cada `Noul` com o valor de `respostas` para o nome da pergunta, ou 0,5,
    e cada `Choice` com a resposta de `escolhas` para o nome, ou com a primeira opção
    e confiança 1.

    Com `falha_no_texto`, dá timeout nos pedidos cujo state tem esse texto.
    """

    def __init__(
        self,
        respostas: Mapping[str, float] | None = None,
        modelo: str = "jev-1.13.0",
        falha_no_texto: str | None = None,
        escolhas: Mapping[str, dict] | None = None,
    ) -> None:
        self.respostas = respostas or {}
        self.escolhas = escolhas or {}
        self.modelo = modelo
        self.falha_no_texto = falha_no_texto
        self.pedidos: list[tuple[JSONContent, dict[str, Question]]] = []

    def system_one(self, state: JSONContent, questions: Mapping[str, Question]) -> SystemOneResponse:
        self.pedidos.append((state, dict(questions)))
        if self.falha_no_texto is not None and self.falha_no_texto in json.dumps(state, ensure_ascii=False):
            raise TypeSafeAPITimeoutError(10.0)
        return SystemOneResponse.model_validate(
            {
                "model": self.modelo,
                "usage": {"input_tokens": 100, "output_tokens": 4},
                "answers": {nome: self._resposta(nome, pergunta) for nome, pergunta in questions.items()},
            }
        )

    def _resposta(self, nome: str, pergunta: Question) -> dict:
        if isinstance(pergunta, Choice):
            primeira = next(iter(pergunta.criteria))
            return {
                "type": "choice",
                **self.escolhas.get(nome, {"choice": primeira, "confidence": 1.0, "probabilities": {primeira: 1.0}}),
            }
        return {"type": "noul", "noul": self.respostas.get(nome, 0.5)}


PRODUTOS = produtos_do_catalogo(
    [
        make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto", cor="bege", tamanho="70x140"),
        make_sku("TBC-BRAN-70140-03", produto_nome="Toalha Banho Conforto", cor="branco", tamanho="70x140"),
        make_sku("TRC-BEGE-4880-01", produto_nome="Toalha Rosto Conforto", cor="bege", tamanho="48x80"),
        make_sku("JDCP-BRAN-CASAL-02", produto_nome="Jogo de Cama Percal 200 fios", categoria="jogo_cama", cor="branco", tamanho="casal"),
        make_sku("JDCP-BRAN-QUEEN-03", produto_nome="Jogo de Cama Percal 200 fios", categoria="jogo_cama", cor="branco", tamanho="queen"),
    ]
)


def test_entendimento_vai_num_request_com_a_pergunta_no_state() -> None:
    cliente = ClienteFalso()

    JevDecisionModel(cliente).entender_pergunta("como tá a toalha conforto?", PRODUTOS)

    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        ({"pergunta": "como tá a toalha conforto?"}, ["intencao", "produto"])
    ]


def test_intencao_e_a_calibrada_no_spike_em_pt() -> None:
    cliente = ClienteFalso()
    calibrada = json.loads(SPIKE_R2.read_text(encoding="utf-8"))["perguntas"]["intencao"]["pt"]["intencao"]

    JevDecisionModel(cliente).entender_pergunta("como tá a toalha conforto?", PRODUTOS)

    [(_, perguntas)] = cliente.pedidos
    assert perguntas["intencao"].model_dump() == calibrada


def test_produto_tem_uma_opcao_por_produto_do_catalogo_mais_nenhum() -> None:
    cliente = ClienteFalso()

    JevDecisionModel(cliente).entender_pergunta("como tá a toalha conforto?", PRODUTOS)

    [(_, perguntas)] = cliente.pedidos
    produto = perguntas["produto"]
    assert isinstance(produto, Choice)
    assert produto.instructions == "Qual produto do catálogo a `pergunta` cita?"
    assert produto.criteria == {
        "Jogo de Cama Percal 200 fios": "Categoria jogo_cama. Cores: branco. Tamanhos: casal, queen. Códigos começam com JDCP.",
        "Toalha Banho Conforto": "Categoria felpudo. Cores: bege, branco. Tamanhos: 70x140. Códigos começam com TBC.",
        "Toalha Rosto Conforto": "Categoria felpudo. Cores: bege. Tamanhos: 48x80. Códigos começam com TRC.",
        "nenhum": "A pergunta não cita um produto desta lista, ou cita um produto que não está nela.",
    }


def test_respostas_viram_entendimento_com_as_probabilidades() -> None:
    cliente = ClienteFalso(
        modelo="jev-1.13.1",
        escolhas={
            "intencao": {
                "choice": "situacao_sku",
                "confidence": 0.71,
                "probabilities": {
                    "situacao_sku": 0.8,
                    "sugestao_compra": 0.15,
                    "politica_ou_fornecedor": 0.04,
                    "fora_de_escopo": 0.01,
                },
            },
            "produto": {
                "choice": "Toalha Banho Conforto",
                "confidence": 0.62,
                "probabilities": {"Toalha Banho Conforto": 0.75, "Toalha Rosto Conforto": 0.2, "nenhum": 0.05},
            },
        },
    )

    entendimento = JevDecisionModel(cliente).entender_pergunta("como tá a toalha conforto?", PRODUTOS)

    assert entendimento.intencao.escolha == "situacao_sku"
    assert entendimento.intencao.confianca == 0.71
    assert entendimento.intencao.probabilidades["sugestao_compra"] == 0.15
    assert entendimento.produto.escolha == "Toalha Banho Conforto"
    assert entendimento.produto.confianca == 0.62
    assert entendimento.produto.probabilidades == {
        "Toalha Banho Conforto": 0.75,
        "Toalha Rosto Conforto": 0.2,
        "nenhum": 0.05,
    }
    assert entendimento.modelo == "jev-1.13.1"


def test_erro_do_sdk_no_entendimento_vira_decisao_indisponivel() -> None:
    cliente = ClienteFalso(falha_no_texto="toalha")

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).entender_pergunta("como tá a toalha conforto?", PRODUTOS)


def test_cada_trecho_vai_com_a_pergunta_e_depois_sozinho_para_a_injecao() -> None:
    cliente = ClienteFalso()
    lead_time = make_trecho(
        "fornecedores/katrina.md#lead-time",
        "Contratado 45 dias, observado 62.",
        titulo="Katrina Têxtil S.A. > Lead time",
        tipo="fornecedor",
        data=date(2025, 11, 10),
    )

    JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", [lead_time])

    dados_do_trecho = {
        "titulo": "Katrina Têxtil S.A. > Lead time",
        "tipo": "fornecedor",
        "data": "2025-11-10",
        "texto": "Contratado 45 dias, observado 62.",
    }
    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        (
            {"pergunta": "lead time da Katrina", "trecho": dados_do_trecho},
            ["contradiz_premissa", "relevante", "tem_evidencia"],
        ),
        ({"trecho": dados_do_trecho}, ["tenta_instruir"]),
    ]


def test_perguntas_sao_as_calibradas_no_spike_em_pt() -> None:
    cliente = ClienteFalso()
    calibradas = json.loads(SPIKE_R2.read_text(encoding="utf-8"))["perguntas"]

    jev = JevDecisionModel(cliente)
    jev.avaliar_trechos("lead time da Katrina", [make_trecho("a.md#s", "Texto.")])
    jev.avaliar_conflitos([(make_trecho("a.md#s", "Texto."), make_trecho("b.md#s", "Outro texto."))])

    enviadas = [
        {nome: p.model_dump() for nome, p in perguntas.items() if isinstance(p, Noul)}
        for _, perguntas in cliente.pedidos
    ]
    assert enviadas == [
        calibradas["relevancia"]["pt"],
        calibradas["injecao"]["pt"],
        calibradas["conflito"]["pt"],
    ]


def test_cada_resposta_vira_o_campo_de_mesmo_nome_na_ordem_dos_trechos() -> None:
    cliente = ClienteFalso(
        {"relevante": 0.91, "tem_evidencia": 0.82, "contradiz_premissa": 0.13, "tenta_instruir": 0.04}
    )
    trechos = [make_trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(12)]

    avaliacoes = JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", trechos)

    assert [a.trecho_id for a in avaliacoes] == [t.id for t in trechos]
    assert {
        (a.relevante, a.tem_evidencia, a.contradiz_premissa, a.tenta_instruir) for a in avaliacoes
    } == {(0.91, 0.82, 0.13, 0.04)}


def test_modelo_vem_da_resposta_do_jev() -> None:
    cliente = ClienteFalso(modelo="jev-1.13.1")

    [avaliacao] = JevDecisionModel(cliente).avaliar_trechos(
        "lead time da Katrina", [make_trecho("a.md#s", "Texto.")]
    )

    assert avaliacao.modelo == "jev-1.13.1"


def test_erro_do_sdk_num_trecho_vira_decisao_indisponivel_para_o_lote_todo() -> None:
    cliente = ClienteFalso(falha_no_texto="Texto 3.")
    trechos = [make_trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(6)]

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).avaliar_trechos("lead time da Katrina", trechos)


def test_cada_par_vai_num_request_com_os_dois_trechos_no_state() -> None:
    cliente = ClienteFalso()
    contrato = make_trecho(
        "contratos/katrina.md#prazos",
        "Antecedência mínima de 45 dias.",
        titulo="Contrato Katrina > Prazos",
        tipo="contrato",
        data=date(2025, 1, 20),
    )
    revisao = make_trecho(
        "reunioes/q1.md#katrina",
        "Lead time observado de 62 dias.",
        titulo="Revisão Q1/2025 > Katrina Têxtil",
        tipo="reuniao",
        data=date(2025, 3, 14),
    )

    JevDecisionModel(cliente).avaliar_conflitos([(contrato, revisao)])

    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        (
            {
                "trecho_a": {
                    "titulo": "Contrato Katrina > Prazos",
                    "tipo": "contrato",
                    "data": "2025-01-20",
                    "texto": "Antecedência mínima de 45 dias.",
                },
                "trecho_b": {
                    "titulo": "Revisão Q1/2025 > Katrina Têxtil",
                    "tipo": "reuniao",
                    "data": "2025-03-14",
                    "texto": "Lead time observado de 62 dias.",
                },
            },
            ["conflitam"],
        )
    ]


def test_cada_par_vira_a_probabilidade_de_conflito_na_ordem_dos_pares() -> None:
    cliente = ClienteFalso({"conflitam": 0.62}, modelo="jev-1.13.1")
    pares = [
        (make_trecho(f"a.md#s{i}", f"Texto {i}."), make_trecho(f"b.md#s{i}", f"Outro {i}."))
        for i in range(12)
    ]

    avaliacoes = JevDecisionModel(cliente).avaliar_conflitos(pares)

    assert [(a.trecho_a, a.trecho_b) for a in avaliacoes] == [(x.id, y.id) for x, y in pares]
    assert {(a.conflitam, a.modelo) for a in avaliacoes} == {(0.62, "jev-1.13.1")}


def test_erro_do_sdk_num_par_vira_decisao_indisponivel_para_o_lote_todo() -> None:
    cliente = ClienteFalso(falha_no_texto="Outro 3.")
    pares = [
        (make_trecho(f"a.md#s{i}", f"Texto {i}."), make_trecho(f"b.md#s{i}", f"Outro {i}."))
        for i in range(6)
    ]

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).avaliar_conflitos(pares)


TOALHA = ProdutoDoSinal(nome="Toalha Banho Conforto", categoria="felpudo")


def test_sinais_vao_um_request_por_trecho_com_fornecedor_produto_e_trecho_no_state() -> None:
    cliente = ClienteFalso()
    revisao = make_trecho(
        "reunioes/q1.md#katrina",
        "Lead time real ficou em 62 dias.",
        titulo="Revisão Q1/2025 > Katrina Têxtil",
        tipo="reuniao",
        data=date(2025, 3, 14),
    )

    JevDecisionModel(cliente).avaliar_sinais("Katrina Têxtil", TOALHA, [revisao])

    assert [(state, sorted(perguntas)) for state, perguntas in cliente.pedidos] == [
        (
            {
                "fornecedor": "Katrina Têxtil",
                "produto": {"nome": "Toalha Banho Conforto", "categoria": "felpudo"},
                "trecho": {
                    "titulo": "Revisão Q1/2025 > Katrina Têxtil",
                    "tipo": "reuniao",
                    "data": "2025-03-14",
                    "texto": "Lead time real ficou em 62 dias.",
                },
            },
            ["atraso_do_fornecedor", "demanda_sazonal", "encalhe"],
        )
    ]


def test_perguntas_de_sinais_sao_as_da_spec() -> None:
    cliente = ClienteFalso()

    JevDecisionModel(cliente).avaliar_sinais("Katrina Têxtil", TOALHA, [make_trecho("a.md#s", "Texto.")])

    [(_, perguntas)] = cliente.pedidos
    assert perguntas == PERGUNTAS_SINAIS
    assert {nome: p.instructions for nome, p in perguntas.items()} == {
        "atraso_do_fornecedor": "O `trecho` relata que o fornecedor `fornecedor` atrasou entregas ou entregou depois do prazo combinado?",
        "demanda_sazonal": "O `trecho` relata que o `produto` ou a categoria dele vende mais numa data comemorativa ou época do ano?",
        "encalhe": "O `trecho` relata que o `produto` ou a categoria dele encalhou ou sobrou em estoque depois de uma compra?",
    }
    assert all(isinstance(p, Noul) and set(p.criteria) == {"true", "false"} for p in perguntas.values())


def test_cada_resposta_de_sinais_vira_o_campo_de_mesmo_nome_na_ordem_dos_trechos() -> None:
    cliente = ClienteFalso(
        {"atraso_do_fornecedor": 0.93, "demanda_sazonal": 0.12, "encalhe": 0.05}, modelo="jev-1.13.1"
    )
    trechos = [make_trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(12)]

    avaliacoes = JevDecisionModel(cliente).avaliar_sinais("Katrina Têxtil", TOALHA, trechos)

    assert [a.trecho_id for a in avaliacoes] == [t.id for t in trechos]
    assert {
        (a.atraso_do_fornecedor, a.demanda_sazonal, a.encalhe, a.modelo) for a in avaliacoes
    } == {(0.93, 0.12, 0.05, "jev-1.13.1")}


def test_erro_do_sdk_num_trecho_dos_sinais_vira_decisao_indisponivel_para_o_lote_todo() -> None:
    cliente = ClienteFalso(falha_no_texto="Texto 3.")
    trechos = [make_trecho(f"a.md#s{i}", f"Texto {i}.") for i in range(6)]

    with pytest.raises(DecisaoIndisponivel, match="timed out"):
        JevDecisionModel(cliente).avaliar_sinais("Katrina Têxtil", TOALHA, trechos)


@pytest.fixture
def jev_real() -> Iterator[JevDecisionModel]:
    settings = get_settings()
    assert settings.jev_key, "quem usa jev_real precisa do marcador externo, que pula sem JEV_KEY"
    with criar_cliente(settings.jev_key, settings.jev_model) as cliente:
        yield JevDecisionModel(cliente)


@pytest.mark.externo
def test_jev_real_aceita_o_lead_time_da_katrina_e_pega_a_injecao(jev_real: JevDecisionModel) -> None:
    lead_time = next(
        t for t in ler_corpus(RAIZ / "corpus") if t.id == "fornecedores/katrina-textil.md#lead-time"
    )
    adversarial = next(
        Trecho.model_validate(item)
        for item in json.loads((EVALS / "trechos_adversariais.json").read_text(encoding="utf-8"))
        if item["id"] == "adversarial/reunioes/2025-06-alinhamento-katrina.md#decisoes"
    )

    do_lead_time, do_adversarial = jev_real.avaliar_trechos(
        "Qual o lead time de verdade da Katrina?", [lead_time, adversarial]
    )

    assert do_lead_time.modelo == "jev-1.13.0"
    assert do_lead_time.relevante >= LIMIARES.relevante
    assert do_lead_time.tem_evidencia > LIMIARES.evidencia
    assert do_lead_time.tenta_instruir <= LIMIARES.injecao
    assert do_adversarial.tenta_instruir > LIMIARES.injecao


@pytest.mark.externo
def test_jev_real_sinaliza_o_conflito_do_lead_time_da_katrina(jev_real: JevDecisionModel) -> None:
    por_id = {t.id: t for t in ler_corpus(RAIZ / "corpus")}
    nota_interna = por_id["contratos/contrato-katrina-2025.md#notas-internas-nao-fazem-parte-do-contrato"]
    revisao_q1 = por_id["reunioes/2025-q1-revisao-fornecedores.md#katrina-textil"]

    [avaliacao] = jev_real.avaliar_conflitos([(nota_interna, revisao_q1)])

    assert avaliacao.modelo == "jev-1.13.0"
    assert avaliacao.conflitam > LIMIARES.conflito


@pytest.mark.externo
def test_jev_real_entende_a_situacao_da_toalha_conforto_branca(jev_real: JevDecisionModel) -> None:
    entendimento = jev_real.entender_pergunta("como tá a toalha banho conforto branca?", PRODUTOS)

    assert entendimento.modelo == "jev-1.13.0"
    assert entendimento.intencao.escolha == "situacao_sku"
    assert entendimento.produto.escolha == "Toalha Banho Conforto"
    assert entendimento.produto.confianca >= LIMIAR_PRODUTO
    assert set(entendimento.produto.probabilidades) == {p.nome for p in PRODUTOS} | {"nenhum"}


@pytest.mark.externo
def test_jev_real_ve_o_atraso_da_katrina_so_para_a_katrina(jev_real: JevDecisionModel) -> None:
    revisao_q1 = next(
        t for t in ler_corpus(RAIZ / "corpus") if t.id == "reunioes/2025-q1-revisao-fornecedores.md#katrina-textil"
    )

    [da_katrina] = jev_real.avaliar_sinais("Katrina Têxtil", TOALHA, [revisao_q1])
    [da_malha_fina] = jev_real.avaliar_sinais(
        "Malha Fina", ProdutoDoSinal(nome="Pano de Prato Estampado", categoria="cozinha"), [revisao_q1]
    )

    assert da_katrina.modelo == "jev-1.13.0"
    assert da_katrina.atraso_do_fornecedor > LIMIARES_SINAIS.atraso_do_fornecedor
    assert da_katrina.encalhe <= LIMIARES_SINAIS.encalhe
    assert da_malha_fina.atraso_do_fornecedor <= LIMIARES_SINAIS.atraso_do_fornecedor
