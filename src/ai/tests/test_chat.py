"""Testes do `Copilot` com ERP, política, busca, Jev e redator em memória."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from src.ai.busca import BuscaContexto
from src.ai.chat import (
    FAIXAS,
    MAX_TRECHOS_NO_CONTEXTO,
    RESPOSTA_FORA_DE_ESCOPO,
    Copilot,
)
from src.ai.decisao import DecisaoIndisponivel
from src.ai.identificacao import MAX_SKUS_POR_RESPOSTA
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel, InMemoryRegistrosDecisao, Probabilidades
from src.ai.redator import Redator
from src.ai.schemas import Entendimento, RegistroDecisao, Trecho
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.purchasing.service import Purchasing
from src.sales.service import Sales
from tests.fakes import (
    RedatorGravador,
    make_entendimento,
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_sku,
    make_trecho,
    make_venda,
    repositorio_com,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
TOALHA = "Toalha Banho Conforto"
PERCAL = "Jogo de Cama Percal 200"
TOALHA_BEGE = make_sku("TBC-BEGE-70140-01", produto_nome=TOALHA, cor="bege", tamanho="70x140")
TOALHA_BRANCA = make_sku("TBC-BRAN-70140-02", produto_nome=TOALHA, cor="branco", tamanho="70x140")
PERCAL_CASAL = make_sku("JDCP-BRAN-CASAL-01", produto_nome=PERCAL, categoria="cama", cor="branco", tamanho="casal")
KATRINA = make_fornecedor("Katrina Têxtil", lead_time_dias_contratado=35)
PERGUNTA = "Como tá a toalha banho conforto?"


def erp(skus: list[SKU] | None = None, *, sem_estoque: set[str] = frozenset()) -> InMemoryERPAdapter:
    skus = skus or [TOALHA_BEGE, TOALHA_BRANCA, PERCAL_CASAL]
    return InMemoryERPAdapter(
        skus=skus,
        fornecedores=[KATRINA],
        fornecedores_por_sku={
            s.sku_code: [make_fornecedor_sku(KATRINA, preco_unitario_reais=1800, moq_unidades=48)]
            for s in skus
        },
        estoques={s.sku_code: make_estoque(disponivel=40) for s in skus if s.sku_code not in sem_estoque},
        vendas=[
            make_venda(s, datetime(2026, mes, 5, tzinfo=UTC), 100, key=f"{s.sku_code}|{mes}")
            for s in skus
            for mes in range(3, 9)
        ],
    )


def copilot(
    entendimento: Entendimento,
    *,
    redator: Redator | None = None,
    trechos: list[Trecho] | None = None,
    avaliacoes: Mapping[str, Probabilidades] | None = None,
    conflitos: Mapping[tuple[str, str], float] | None = None,
    falhar_entendimento: bool = False,
    falhar_busca: bool = False,
    adapter: InMemoryERPAdapter | None = None,
    registros: InMemoryRegistrosDecisao | None = None,
) -> Copilot:
    """Com `falhar_busca`, o Jev falha se a busca no corpus for chamada."""
    adapter = adapter or erp()
    catalog = Catalog(adapter)
    sales = Sales(adapter, now=NOW)
    inventory = Inventory(adapter, sales)
    ficha_sku = FichaSKU(catalog, inventory, sales)
    politicas = InMemoryPoliticaCompraRepositorio(now=NOW)
    decisao = InMemoryDecisionModel(
        avaliacoes,
        conflitos=conflitos,
        entendimento_padrao=entendimento,
        falhar_entendimento=falhar_entendimento,
        falhar_trechos=falhar_busca,
        falhar_conflitos=falhar_busca,
    )
    embedder = FakeEmbedder()
    busca = BuscaContexto(embedder, repositorio_com(trechos or [], embedder), decisao)
    return Copilot(
        decisao,
        catalog,
        ficha_sku,
        Purchasing(ficha_sku, inventory, sales, politicas, now=NOW),
        politicas,
        busca,
        redator or RedatorGravador(),
        registros if registros is not None else InMemoryRegistrosDecisao(),
    )


def contexto_de(redator: RedatorGravador) -> str:
    [(_, contexto)] = redator.chamadas
    return contexto


ACEITO: Probabilidades = {"relevante": 0.9, "tem_evidencia": 0.9}
CONFLITANTE: Probabilidades = {"relevante": 0.9, "contradiz_premissa": 0.95}
DESCARTADO: Probabilidades = {"relevante": 0.1}


def test_situacao_do_sku_pelo_codigo_redige_com_a_ficha_e_a_politica() -> None:
    redator = RedatorGravador("A toalha bege tem 40 unidades.")
    pergunta = "Qual a situação do SKU TBC-BEGE-70140-01?"

    resposta = copilot(make_entendimento("situacao_sku", 0.95), redator=redator, falhar_busca=True).responder(
        pergunta
    )

    assert resposta.resposta == "A toalha bege tem 40 unidades."
    assert resposta.acao == "respondeu"
    assert resposta.faixa == "alta"
    assert resposta.redator == "gravador"
    assert resposta.identificacao is not None
    assert resposta.identificacao.origem == "codigo"
    assert [f.sku.sku_code for f in resposta.fichas] == ["TBC-BEGE-70140-01"]
    assert resposta.sugestoes == resposta.trechos == resposta.conflitos == []
    [(pergunta_redigida, contexto)] = redator.chamadas
    assert pergunta_redigida == pergunta
    assert "## Fichas de SKU (dados do ERP)" in contexto
    assert "### TBC-BEGE-70140-01" in contexto
    assert "## Política de compra ativa (v1)" in contexto
    assert "## Trechos do corpus" not in contexto


def test_situacao_do_sku_pelo_produto_do_jev_estreita_pela_cor() -> None:
    entendimento = make_entendimento("situacao_sku", 0.95, produto=TOALHA, confianca_produto=0.9)

    resposta = copilot(entendimento).responder("Como tá a toalha banho conforto bege?")

    assert resposta.identificacao is not None
    assert resposta.identificacao.origem == "produto"
    assert [f.sku.sku_code for f in resposta.fichas] == ["TBC-BEGE-70140-01"]


def test_situacao_do_sku_sem_sku_identificado_pede_o_codigo_sem_chamar_o_redator() -> None:
    redator = RedatorGravador()

    resposta = copilot(make_entendimento("situacao_sku", 0.95), redator=redator).responder("Como tá o estoque?")

    assert resposta.resposta == (
        "Não identifiquei o produto no catálogo. Informe o código do SKU (ex: TBC-BEGE-70140-01) "
        "ou o nome do produto."
    )
    assert resposta.acao == "pediu_esclarecimento"
    assert resposta.redator is None
    assert resposta.identificacao is not None
    assert resposta.identificacao.origem == "nenhum"
    assert resposta.fichas == []
    assert redator.chamadas == []


def test_esclarecimento_de_sku_cita_os_candidatos() -> None:
    entendimento = make_entendimento(
        "situacao_sku",
        0.95,
        produto=TOALHA,
        confianca_produto=0.45,
        probabilidades_produto={TOALHA: 0.45, PERCAL: 0.35, "nenhum": 0.2},
    )

    resposta = copilot(entendimento).responder(PERGUNTA)

    assert resposta.resposta.endswith(f"ou o nome do produto. Você quer dizer {TOALHA} ou {PERCAL}?")
    assert resposta.acao == "pediu_esclarecimento"


def test_sku_sem_estoque_vira_observacao() -> None:
    redator = RedatorGravador()
    adapter = erp(sem_estoque={"TBC-BRAN-70140-02"})
    entendimento = make_entendimento("situacao_sku", 0.95, produto=TOALHA, confianca_produto=0.9)

    resposta = copilot(entendimento, redator=redator, adapter=adapter).responder(PERGUNTA)

    assert [f.sku.sku_code for f in resposta.fichas] == ["TBC-BEGE-70140-01"]
    assert "- O SKU TBC-BRAN-70140-02 não tem registro de estoque no ERP." in contexto_de(redator)


def test_lista_de_skus_cortada_vira_observacao() -> None:
    skus = [
        make_sku(f"TBC-C{i:02d}-70140-{i:02d}", produto_nome=TOALHA, cor=f"cor{i}")
        for i in range(MAX_SKUS_POR_RESPOSTA + 1)
    ]
    redator = RedatorGravador()
    entendimento = make_entendimento("situacao_sku", 0.95, produto=TOALHA, confianca_produto=0.9)

    resposta = copilot(entendimento, redator=redator, adapter=erp(skus)).responder(PERGUNTA)

    assert len(resposta.fichas) == MAX_SKUS_POR_RESPOSTA
    assert (
        f"- A pergunta corresponde a {MAX_SKUS_POR_RESPOSTA + 1} SKUs; "
        f"os dados abaixo trazem só os {MAX_SKUS_POR_RESPOSTA} primeiros."
    ) in contexto_de(redator)


def test_sugestao_de_compra_redige_com_as_sugestoes_a_politica_e_os_trechos() -> None:
    redator = RedatorGravador()
    pergunta = "Quanto comprar do TBC-BEGE-70140-01?"

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho("politicas/compra.md#teto")],
        avaliacoes={"politicas/compra.md#teto": ACEITO},
    ).responder(pergunta)

    assert resposta.acao == "respondeu"
    assert [s.sku_code for s in resposta.sugestoes] == ["TBC-BEGE-70140-01"]
    assert resposta.sugestoes[0].quantidade > 0
    assert resposta.fichas == []
    assert [t.id for t in resposta.trechos] == ["politicas/compra.md#teto"]
    contexto = contexto_de(redator)
    assert "## Sugestões de pedido (cálculo da política de compra)" in contexto
    assert "## Política de compra ativa (v1)" in contexto
    assert '<trecho id="politicas/compra.md#teto"' in contexto


def test_sugestao_de_compra_sem_sku_busca_e_avisa_que_a_quantidade_depende_do_sku() -> None:
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho("politicas/compra.md#teto")],
        avaliacoes={"politicas/compra.md#teto": ACEITO},
    ).responder("O que comprar para o Natal?")

    assert resposta.acao == "respondeu"
    assert resposta.sugestoes == []
    assert [t.id for t in resposta.trechos] == ["politicas/compra.md#teto"]
    assert "a quantidade da sugestão depende de um SKU do catálogo" in contexto_de(redator)


def test_politica_ou_fornecedor_redige_so_com_a_busca() -> None:
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=redator,
        trechos=[make_trecho("fornecedores/katrina.md#lead-time")],
        avaliacoes={"fornecedores/katrina.md#lead-time": ACEITO},
    ).responder("Qual o lead time da Katrina? TBC-BEGE-70140-01")

    assert resposta.acao == "respondeu"
    assert resposta.identificacao is None
    assert resposta.fichas == resposta.sugestoes == []
    assert [t.id for t in resposta.trechos] == ["fornecedores/katrina.md#lead-time"]
    contexto = contexto_de(redator)
    assert "## Trechos do corpus" in contexto
    assert "## Política de compra" not in contexto
    assert "## Fichas de SKU" not in contexto


def test_fora_de_escopo_responde_texto_fixo_sem_busca_nem_redator() -> None:
    redator = RedatorGravador()

    resposta = copilot(make_entendimento("fora_de_escopo", 0.95), redator=redator, falhar_busca=True).responder(
        "Quem ganhou o jogo ontem?"
    )

    assert resposta.resposta == RESPOSTA_FORA_DE_ESCOPO
    assert resposta.resposta == (
        "Só consigo ajudar com as compras do atacadista: situação de SKU, sugestão de pedido, "
        "política de compra e fornecedores."
    )
    assert resposta.acao == "fora_de_escopo"
    assert resposta.redator is None
    assert redator.chamadas == []


def test_fora_de_escopo_na_faixa_media_tambem_e_resposta_fixa() -> None:
    resposta = copilot(make_entendimento("fora_de_escopo", 0.6)).responder("Quem ganhou o jogo ontem?")

    assert resposta.resposta == RESPOSTA_FORA_DE_ESCOPO
    assert resposta.faixa == "media"
    assert resposta.acao == "fora_de_escopo"


@pytest.mark.parametrize(
    ("confianca", "faixa", "acao"),
    [
        pytest.param(1.0, "alta", "respondeu", id="1,00"),
        pytest.param(FAIXAS.alta, "alta", "respondeu", id="no-limiar-alto"),
        pytest.param(0.79, "media", "confirmou_e_respondeu", id="0,79"),
        pytest.param(FAIXAS.media, "media", "confirmou_e_respondeu", id="no-limiar-medio"),
        pytest.param(0.49, "baixa", "pediu_esclarecimento", id="0,49"),
    ],
)
def test_faixa_pela_confianca_da_intencao(confianca: float, faixa: str, acao: str) -> None:
    resposta = copilot(make_entendimento("politica_ou_fornecedor", confianca)).responder(PERGUNTA)

    assert resposta.faixa == faixa
    assert resposta.acao == acao


def test_faixa_media_comeca_confirmando_o_entendimento() -> None:
    redator = RedatorGravador("Lead time de 45 dias.")

    resposta = copilot(make_entendimento("politica_ou_fornecedor", 0.6), redator=redator).responder(PERGUNTA)

    assert resposta.resposta == (
        "Entendi que você quer saber da política de compra e dos fornecedores. "
        "Se não for isso, reformule a pergunta.\n\nLead time de 45 dias."
    )
    assert resposta.redator == "gravador"


def test_faixa_baixa_pede_esclarecimento_com_as_duas_intencoes_mais_provaveis() -> None:
    redator = RedatorGravador()
    entendimento = make_entendimento(
        "situacao_sku",
        0.31,
        probabilidades_intencao={
            "situacao_sku": 0.40,
            "sugestao_compra": 0.10,
            "politica_ou_fornecedor": 0.35,
            "fora_de_escopo": 0.15,
        },
    )

    resposta = copilot(entendimento, redator=redator, falhar_busca=True).responder(PERGUNTA)

    assert resposta.resposta == (
        "Não entendi bem o que você precisa. Você quer ver a situação de um SKU (estoque, giro e cobertura) "
        "ou saber da política de compra e dos fornecedores? Pode reformular a pergunta?"
    )
    assert resposta.acao == "pediu_esclarecimento"
    assert resposta.faixa == "baixa"
    assert resposta.identificacao is None
    assert resposta.redator is None
    assert redator.chamadas == []


def test_queda_do_redator_cai_no_sem_llm_com_a_observacao() -> None:
    redator = RedatorGravador(nome="groq:modelo", falhar=True)

    resposta = copilot(make_entendimento("situacao_sku", 0.95), redator=redator).responder(
        "Situação do TBC-BEGE-70140-01"
    )

    assert resposta.acao == "respondeu"
    assert resposta.redator == "sem_llm"
    assert resposta.resposta.startswith("O LLM que redige a resposta está indisponível no momento.")
    assert "### TBC-BEGE-70140-01" in resposta.resposta
    assert resposta.resposta.endswith("- O redator groq:modelo falhou; a resposta vai sem redação.")


def test_jev_fora_do_ar_propaga_decisao_indisponivel_sem_registro() -> None:
    redator = RedatorGravador()
    registros = InMemoryRegistrosDecisao()

    with pytest.raises(DecisaoIndisponivel):
        copilot(
            make_entendimento(), redator=redator, falhar_entendimento=True, registros=registros
        ).responder(PERGUNTA)
    assert redator.chamadas == []
    assert registros.listar(10) == []


def test_so_trechos_aceitos_e_conflitantes_chegam_ao_contexto_ate_o_maximo() -> None:
    aceitos = [f"aceitos.md#a{i}" for i in range(MAX_TRECHOS_NO_CONTEXTO - 2)]
    conflitantes = [f"conflitantes.md#c{i}" for i in range(4)]
    descartados = [f"descartados.md#d{i}" for i in range(3)]
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=redator,
        trechos=[make_trecho(i) for i in aceitos + conflitantes + descartados],
        avaliacoes={
            **{i: ACEITO for i in aceitos},
            **{i: CONFLITANTE for i in conflitantes},
            **{i: DESCARTADO for i in descartados},
        },
    ).responder(PERGUNTA)

    ids = [t.id for t in resposta.trechos]
    assert len(ids) == MAX_TRECHOS_NO_CONTEXTO
    assert set(ids[: len(aceitos)]) == set(aceitos)
    assert set(ids[len(aceitos) :]) < set(conflitantes)
    contexto = contexto_de(redator)
    assert all(f'<trecho id="{i}"' in contexto for i in ids)
    assert not any(i in contexto for i in descartados)


def test_so_conflitos_entre_trechos_que_foram_ao_contexto() -> None:
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=redator,
        trechos=[make_trecho("contratos/katrina.md#prazos"), make_trecho("reunioes/q1.md#katrina")],
        avaliacoes={"contratos/katrina.md#prazos": ACEITO, "reunioes/q1.md#katrina": ACEITO},
        conflitos={("contratos/katrina.md#prazos", "reunioes/q1.md#katrina"): 0.62},
    ).responder(PERGUNTA)

    [conflito] = resposta.conflitos
    assert {conflito.trecho_a, conflito.trecho_b} == {"contratos/katrina.md#prazos", "reunioes/q1.md#katrina"}
    assert "## Conflitos entre trechos" in contexto_de(redator)


def test_resposta_redigida_grava_o_registro_e_devolve_o_id() -> None:
    registros = InMemoryRegistrosDecisao()
    entendimento = make_entendimento("situacao_sku", 0.95, produto=TOALHA, confianca_produto=0.9)
    pergunta = "Como tá a toalha banho conforto bege?"

    resposta = copilot(
        entendimento, redator=RedatorGravador("A toalha bege tem 40 unidades."), registros=registros
    ).responder(pergunta)

    [registro] = registros.listar(10)
    assert registro.id == resposta.registro_id
    assert registro.model_dump(exclude={"id", "criado_em", "duracao_ms"}) == {
        "pergunta": pergunta,
        "intencao": "situacao_sku",
        "confianca": 0.95,
        "faixa": "alta",
        "acao": "respondeu",
        "skus": ["TBC-BEGE-70140-01"],
        "entendimento": entendimento.model_dump(),
        "trechos": [],
        "redator": "gravador",
        "resposta": "A toalha bege tem 40 unidades.",
    }
    assert registro.criado_em.tzinfo is not None
    assert registro.duracao_ms >= 0


def test_registro_guarda_os_ids_dos_trechos_que_foram_ao_redator() -> None:
    registros = InMemoryRegistrosDecisao()

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        trechos=[make_trecho("contratos/katrina.md#prazos"), make_trecho("descartados.md#d")],
        avaliacoes={"contratos/katrina.md#prazos": ACEITO, "descartados.md#d": DESCARTADO},
        registros=registros,
    ).responder(PERGUNTA)

    [registro] = registros.listar(10)
    assert registro.trechos == [t.id for t in resposta.trechos] == ["contratos/katrina.md#prazos"]


def test_confirmacao_e_queda_do_redator_ficam_no_registro() -> None:
    registros = InMemoryRegistrosDecisao()

    resposta = copilot(
        make_entendimento("situacao_sku", 0.6),
        redator=RedatorGravador(nome="groq:modelo", falhar=True),
        registros=registros,
    ).responder("Situação do TBC-BEGE-70140-01")

    [registro] = registros.listar(10)
    assert (registro.faixa, registro.acao, registro.redator) == ("media", "confirmou_e_respondeu", "sem_llm")
    assert registro.resposta == resposta.resposta


@pytest.mark.parametrize(
    ("entendimento", "pergunta", "acao"),
    [
        pytest.param(make_entendimento("situacao_sku", 0.31), PERGUNTA, "pediu_esclarecimento", id="intencao"),
        pytest.param(make_entendimento("situacao_sku", 0.95), "Como tá o estoque?", "pediu_esclarecimento", id="sku"),
        pytest.param(make_entendimento("fora_de_escopo", 0.95), "Quem ganhou o jogo?", "fora_de_escopo", id="fora-de-escopo"),
    ],
)
def test_resposta_em_codigo_tambem_grava_o_registro(entendimento: Entendimento, pergunta: str, acao: str) -> None:
    registros = InMemoryRegistrosDecisao()

    resposta = copilot(entendimento, registros=registros, falhar_busca=True).responder(pergunta)

    [registro] = registros.listar(10)
    assert registro.id == resposta.registro_id
    assert registro.acao == acao
    assert registro.skus == []
    assert registro.trechos == []
    assert registro.redator is None
    assert registro.resposta == resposta.resposta


def test_cada_pergunta_grava_um_registro_proprio() -> None:
    registros = InMemoryRegistrosDecisao()
    instancia = copilot(make_entendimento("fora_de_escopo", 0.95), registros=registros)

    primeira = instancia.responder("Quem ganhou o jogo?")
    segunda = instancia.responder("Vai chover amanhã?")

    assert primeira.registro_id != segunda.registro_id
    assert [r.pergunta for r in registros.listar(10)] == ["Vai chover amanhã?", "Quem ganhou o jogo?"]


class RegistrosForaDoAr(InMemoryRegistrosDecisao):
    def gravar(self, registro: RegistroDecisao) -> None:
        raise ConnectionError("banco fora do ar")


def test_falha_ao_gravar_o_registro_derruba_a_resposta() -> None:
    with pytest.raises(ConnectionError):
        copilot(make_entendimento("fora_de_escopo", 0.95), registros=RegistrosForaDoAr()).responder(PERGUNTA)
