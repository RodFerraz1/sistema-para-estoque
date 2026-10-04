"""Testes do `Copilot` com ERP, política, busca, Jev e redator em memória."""
from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.ai.busca import BuscaContexto
from src.ai.chat import (
    AVISO_SEM_VERIFICACAO,
    FAIXAS,
    MAX_TRECHOS_NO_CONTEXTO,
    OBSERVACAO_SEM_SINAIS,
    RESPOSTA_FORA_DE_ESCOPO,
    Copilot,
)
from src.ai.decisao import DecisaoIndisponivel
from src.ai.identificacao import MAX_SKUS_POR_RESPOSTA
from src.ai.in_memory import (
    FakeEmbedder,
    InMemoryDecisionModel,
    InMemoryRegistrosDecisao,
    Probabilidades,
)
from src.ai.redator import Redator, RedatorSemLLM
from src.ai.schemas import AvaliacaoTrecho, Entendimento, Escolha, RegistroDecisao, Relacao, SinaisDoSKU, TipoSinal, Trecho
from src.ai.sinais import SinaisCorpus
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.notificacoes.in_memory import InMemoryEpisodiosRepositorio
from src.notificacoes.service import Notificacoes
from src.painel.in_memory import InMemoryAvisosRepositorio, InMemoryCobrancasRepositorio, InMemoryDecisoesRepositorio
from src.painel.schemas import Aviso, TipoAviso
from src.painel.service import Painel
from src.usuarios.in_memory import InMemoryUsuariosRepositorio
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.purchasing.service import Purchasing
from src.reposicao.in_memory import (
    InMemoryAvisosGondolaRepositorio,
    InMemorySetoresRepositorio,
    InMemoryVerificacoesRepositorio,
)
from src.reposicao.service import Reposicao
from src.sales.service import Sales
from tests.fakes import (
    RedatorGravador,
    make_entendimento,
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_relacao,
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


def erp(
    skus: list[SKU] | None = None, *, sem_estoque: set[str] = frozenset(), disponivel: int = 40
) -> InMemoryERPAdapter:
    skus = skus or [TOALHA_BEGE, TOALHA_BRANCA, PERCAL_CASAL]
    return InMemoryERPAdapter(
        skus=skus,
        fornecedores=[KATRINA],
        fornecedores_por_sku={
            s.sku_code: [make_fornecedor_sku(KATRINA, preco_unitario_reais=1800, moq_unidades=48)]
            for s in skus
        },
        estoques={s.sku_code: make_estoque(disponivel=disponivel) for s in skus if s.sku_code not in sem_estoque},
        vendas=[
            make_venda(s, datetime(2026, mes, 5, tzinfo=UTC), 100, key=f"{s.sku_code}|{mes}")
            for s in skus
            for mes in range(3, 9)
        ],
    )


class DecisaoComTrechosSoNosSinais(InMemoryDecisionModel):
    """Descarta os trechos de `so_nos_sinais` em toda busca que não é a focada dos sinais."""

    def __init__(self, *args, so_nos_sinais: Collection[str], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._so_nos_sinais = set(so_nos_sinais)

    def avaliar_trechos(self, pergunta: str, trechos: Sequence[Trecho]) -> list[AvaliacaoTrecho]:
        avaliacoes = super().avaliar_trechos(pergunta, trechos)
        if "atrasos de entrega, vendas por época do ano e estoque encalhado" in pergunta:
            return avaliacoes
        return [
            a.model_copy(update={"relevante": 0.0}) if a.trecho_id in self._so_nos_sinais else a for a in avaliacoes
        ]


def copilot(
    entendimento: Entendimento,
    *,
    redator: Redator | None = None,
    trechos: list[Trecho] | None = None,
    avaliacoes: Mapping[str, Probabilidades] | None = None,
    conflitos: Mapping[tuple[str, str], float] | None = None,
    sinais: Mapping[str, Mapping[TipoSinal, float]] | None = None,
    citacoes: Mapping[str, Escolha[Relacao]] | None = None,
    falhar_entendimento: bool = False,
    falhar_busca: bool = False,
    falhar_sinais: bool = False,
    falhar_citacoes: bool = False,
    so_nos_sinais: Collection[str] = (),
    adapter: InMemoryERPAdapter | None = None,
    registros: InMemoryRegistrosDecisao | None = None,
    avisos: Sequence[Aviso] = (),
) -> Copilot:
    """Com `falhar_busca`, o Jev falha se a busca no corpus for chamada. Os trechos de
    `so_nos_sinais` só são aceitos na busca focada dos sinais."""
    adapter = adapter or erp()
    catalog = Catalog(adapter)
    sales = Sales(adapter, now=NOW)
    inventory = Inventory(adapter, sales)
    ficha_sku = FichaSKU(catalog, inventory, sales)
    politicas = InMemoryPoliticaCompraRepositorio(now=NOW)
    purchasing = Purchasing(catalog, ficha_sku, politicas, adapter, now=NOW)
    repositorio_avisos = InMemoryAvisosRepositorio()
    for aviso in avisos:
        repositorio_avisos.gravar(aviso)
    notificacoes = Notificacoes(InMemoryEpisodiosRepositorio(), InMemoryUsuariosRepositorio(), relogio=lambda: NOW)
    painel = Painel(
        catalog,
        ficha_sku,
        inventory,
        purchasing,
        politicas,
        repositorio_avisos,
        InMemoryDecisoesRepositorio(),
        InMemoryCobrancasRepositorio(),
        notificacoes,
        Reposicao(
            catalog,
            inventory,
            sales,
            politicas,
            InMemoryVerificacoesRepositorio(),
            InMemorySetoresRepositorio(),
            InMemoryAvisosGondolaRepositorio(),
            notificacoes,
            relogio=lambda: NOW,
        ),
        relogio=lambda: NOW,
    )
    decisao = DecisaoComTrechosSoNosSinais(
        avaliacoes,
        so_nos_sinais=so_nos_sinais,
        conflitos=conflitos,
        entendimento_padrao=entendimento,
        falhar_entendimento=falhar_entendimento,
        falhar_trechos=falhar_busca,
        falhar_conflitos=falhar_busca,
        sinais=sinais,
        citacoes=citacoes,
        falhar_sinais=falhar_sinais,
        falhar_citacoes=falhar_citacoes,
    )
    embedder = FakeEmbedder()
    busca = BuscaContexto(embedder, repositorio_com(trechos or [], embedder), decisao)
    return Copilot(
        decisao,
        catalog,
        ficha_sku,
        purchasing,
        politicas,
        painel,
        busca,
        SinaisCorpus(busca, decisao),
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
    assert [s.sugestao.sku_code for s in resposta.sugestoes] == ["TBC-BEGE-70140-01"]
    assert resposta.sugestoes[0].sugestao.quantidade > 0
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


def aviso(sku: SKU, tipo: TipoAviso = "vendendo_muito", comentario: str | None = None) -> Aviso:
    return Aviso(
        id=uuid4(),
        sku_code=sku.sku_code,
        tipo=tipo,
        comentario=comentario,
        avisado_por="Rodrigo",
        usuario_id=None,
        criado_em=NOW,
    )


def test_alertas_e_avisos_redige_com_o_painel_sem_busca() -> None:
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("alertas_e_avisos", 0.95),
        redator=redator,
        avisos=[aviso(TOALHA_BEGE, comentario="Muita gente pedindo")],
        falhar_busca=True,
    ).responder("Algum vendedor pediu algum item?")

    assert resposta.acao == "respondeu"
    assert resposta.identificacao is not None
    assert resposta.identificacao.origem == "nenhum"
    assert resposta.fichas == resposta.sugestoes == resposta.trechos == []
    contexto = contexto_de(redator)
    assert "## Painel de alertas (calculado agora)" in contexto
    assert "3 SKUs no painel: 1 com aviso aberto da equipe de vendas e 2 sem aviso, só por motivo de alerta." in contexto
    assert '  - Vendendo muito, avisado por Rodrigo em 15/09/2026: "Muita gente pedindo"' in contexto
    assert all(f"### {s.sku_code}" in contexto for s in (TOALHA_BEGE, TOALHA_BRANCA, PERCAL_CASAL))
    assert "## Fichas de SKU" not in contexto
    assert "## Trechos do corpus" not in contexto


def test_alertas_e_avisos_de_produto_citado_traz_so_os_skus_dele() -> None:
    redator = RedatorGravador()

    copilot(
        make_entendimento("alertas_e_avisos", 0.95, produto=PERCAL), redator=redator, falhar_busca=True
    ).responder("O jogo de cama percal tem aviso?")

    contexto = contexto_de(redator)
    assert "### JDCP-BRAN-CASAL-01" in contexto
    assert "TBC-BEGE-70140-01" not in contexto
    assert "1 SKU no painel: nenhum com aviso aberto da equipe de vendas e 1 sem aviso, só por motivo de alerta." in contexto


def test_alertas_e_avisos_nao_usa_o_sku_da_tela() -> None:
    redator = RedatorGravador()

    copilot(make_entendimento("alertas_e_avisos", 0.95), redator=redator, falhar_busca=True).responder(
        "Algum vendedor pediu algum item?", sku_em_contexto="JDCP-BRAN-CASAL-01"
    )

    contexto = contexto_de(redator)
    assert "### TBC-BEGE-70140-01" in contexto
    assert "tela do SKU" not in contexto


def test_alertas_e_avisos_com_painel_vazio_vira_observacao() -> None:
    redator = RedatorGravador()

    copilot(
        make_entendimento("alertas_e_avisos", 0.95), redator=redator, adapter=erp(disponivel=500), falhar_busca=True
    ).responder("Tem algo pedindo atenção?")

    contexto = contexto_de(redator)
    assert "## Painel de alertas" not in contexto
    assert "Nenhum SKU está no painel de alertas agora: sem aviso aberto da equipe de vendas" in contexto


def test_fora_de_escopo_responde_texto_fixo_sem_busca_nem_redator() -> None:
    redator = RedatorGravador()

    resposta = copilot(make_entendimento("fora_de_escopo", 0.95), redator=redator, falhar_busca=True).responder(
        "Quem ganhou o jogo ontem?"
    )

    assert resposta.resposta == RESPOSTA_FORA_DE_ESCOPO
    assert resposta.resposta == (
        "Só consigo ajudar com as compras do atacadista: situação de SKU, sugestão de pedido, "
        "política de compra, fornecedores, painel de alertas e avisos da equipe de vendas."
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
    redator = RedatorGravador(nome="anthropic:modelo", falhar=True)

    resposta = copilot(make_entendimento("situacao_sku", 0.95), redator=redator).responder(
        "Situação do TBC-BEGE-70140-01"
    )

    assert resposta.acao == "respondeu"
    assert resposta.redator == "sem_llm"
    assert resposta.resposta.startswith("O LLM que redige a resposta está indisponível no momento.")
    assert "### TBC-BEGE-70140-01" in resposta.resposta
    assert resposta.resposta.endswith("- O redator anthropic:modelo falhou; a resposta vai sem redação.")


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
        "sinais": [],
        "citacoes": [],
        "sku_em_contexto": None,
        "usuario_id": None,
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
        redator=RedatorGravador(nome="anthropic:modelo", falhar=True),
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


SUGESTAO = "Quanto comprar do TBC-BEGE-70140-01?"
LEAD_TIME = "fornecedores/katrina.md#lead-time"
POLITICA_TETO = "politicas/compra.md#teto"


def test_sugestao_de_compra_traz_os_sinais_no_contexto_e_na_resposta() -> None:
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho(LEAD_TIME, "Katrina Têxtil atrasou as entregas da toalha")],
        avaliacoes={LEAD_TIME: ACEITO},
        sinais={LEAD_TIME: {"atraso_do_fornecedor": 0.97}},
    ).responder(SUGESTAO)

    [com_sinais] = resposta.sugestoes
    [sinal] = com_sinais.sinais
    assert (sinal.tipo, sinal.trechos) == ("atraso_do_fornecedor", [LEAD_TIME])
    assert com_sinais.sugestao.quantidade > 0
    contexto = contexto_de(redator)
    assert (
        "- Sinais do corpus (não alteram a quantidade):\n"
        "  - Os documentos relatam atraso de entrega da Katrina Têxtil. "
        f"Trechos de origem: [{LEAD_TIME}]"
    ) in contexto
    assert f'<trecho id="{LEAD_TIME}"' in contexto


def test_sinais_nao_mudam_a_quantidade_da_sugestao() -> None:
    def quantidade(sinais: Mapping[str, Mapping[TipoSinal, float]]) -> int:
        resposta = copilot(
            make_entendimento("sugestao_compra", 0.95),
            trechos=[make_trecho(LEAD_TIME)],
            avaliacoes={LEAD_TIME: ACEITO},
            sinais=sinais,
        ).responder(SUGESTAO)
        return resposta.sugestoes[0].sugestao.quantidade

    assert quantidade({LEAD_TIME: {"atraso_do_fornecedor": 0.99, "encalhe": 0.99}}) == quantidade({})


def test_trechos_de_origem_dos_sinais_entram_depois_dos_da_pergunta_ate_o_maximo() -> None:
    da_pergunta = [f"pergunta.md#p{i}" for i in range(MAX_TRECHOS_NO_CONTEXTO - 1)]
    de_sinais = ["sinais.md#s0", "sinais.md#s1"]
    redator = RedatorGravador()

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho(i) for i in da_pergunta]
        + [make_trecho(i, "Katrina Têxtil e Toalha Banho Conforto: estoque encalhado") for i in de_sinais],
        avaliacoes={i: ACEITO for i in da_pergunta + de_sinais},
        sinais={"sinais.md#s0": {"encalhe": 0.99}, "sinais.md#s1": {"encalhe": 0.9}},
        so_nos_sinais=de_sinais,
    ).responder(SUGESTAO)

    ids = [t.id for t in resposta.trechos]
    assert len(ids) == MAX_TRECHOS_NO_CONTEXTO
    assert set(ids[:-1]) == set(da_pergunta)
    assert ids[-1] == "sinais.md#s0"
    assert resposta.sugestoes[0].sinais[0].trechos == ["sinais.md#s0", "sinais.md#s1"]
    assert "sinais.md#s1" not in contexto_de(redator).split("## Trechos do corpus")[1]


def test_trecho_de_origem_que_nao_coube_no_contexto_ainda_e_verificado_e_nao_inventado() -> None:
    da_pergunta = [f"pergunta.md#p{i}" for i in range(MAX_TRECHOS_NO_CONTEXTO)]
    fora = "sinais.md#fora"
    redator = RedatorGravador(f"A Katrina atrasa [{fora}].")

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho(i, "toalha") for i in da_pergunta] + [make_trecho(fora, "Katrina Têxtil atraso")],
        avaliacoes={**{i: ACEITO for i in da_pergunta}, fora: ACEITO},
        sinais={fora: {"atraso_do_fornecedor": 0.99}},
        citacoes={fora: make_relacao("sustenta")},
        so_nos_sinais=[fora],
    ).responder(SUGESTAO)

    assert fora not in [t.id for t in resposta.trechos]
    assert resposta.sugestoes[0].sinais[0].trechos == [fora]
    [citacao] = resposta.citacoes
    assert (citacao.trecho_id, citacao.veredito) == (fora, "confirmada")
    assert resposta.resposta == f"A Katrina atrasa [{fora}]."


def test_jev_fora_do_ar_nos_sinais_responde_sem_sinais_e_com_a_observacao_no_contexto() -> None:
    redator = RedatorGravador("Compre 120 unidades.")

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=redator,
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
        falhar_sinais=True,
    ).responder(SUGESTAO)

    assert [s.sinais for s in resposta.sugestoes] == [None]
    assert resposta.resposta == "Compre 120 unidades."
    contexto = contexto_de(redator)
    assert f"## Observações\n\n- {OBSERVACAO_SEM_SINAIS}" in contexto
    assert "Sinais do corpus" not in contexto
    assert OBSERVACAO_SEM_SINAIS == (
        "Não foi possível calcular os sinais do corpus agora (o modelo de decisão está indisponível), "
        "então as sugestões vêm sem eles."
    )


def test_resposta_redigida_por_llm_tem_as_citacoes_verificadas_e_marcadas() -> None:
    redacao = f"O teto é de 3 meses [{POLITICA_TETO}]. A Katrina entrega em 30 dias [{LEAD_TIME}]."

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorGravador(redacao),
        trechos=[make_trecho(POLITICA_TETO), make_trecho(LEAD_TIME)],
        avaliacoes={POLITICA_TETO: ACEITO, LEAD_TIME: ACEITO},
        citacoes={POLITICA_TETO: make_relacao("sustenta"), LEAD_TIME: make_relacao("contradiz", 0.97)},
    ).responder(PERGUNTA)

    assert resposta.resposta == (
        f"O teto é de 3 meses [{POLITICA_TETO}]. A Katrina entrega em 30 dias [{LEAD_TIME} - o trecho diz o contrário]."
    )
    assert [(c.trecho_id, c.afirmacao, c.veredito, c.confianca) for c in resposta.citacoes] == [
        (POLITICA_TETO, "O teto é de 3 meses.", "confirmada", 0.95),
        (LEAD_TIME, "A Katrina entrega em 30 dias.", "contradita", 0.97),
    ]


def test_citacao_de_id_fora_do_contexto_e_inventada_sem_chamar_o_jev() -> None:
    inventado = "contratos/inexistente.md#prazos"

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorGravador(f"O prazo é de 45 dias [{inventado}]."),
        falhar_citacoes=True,
    ).responder(PERGUNTA)

    [citacao] = resposta.citacoes
    assert (citacao.veredito, citacao.confianca) == ("inventada", None)
    assert resposta.resposta == f"O prazo é de 45 dias [{inventado} - trecho inexistente]."


def test_jev_fora_do_ar_na_verificacao_marca_as_citacoes_como_incertas_e_avisa() -> None:
    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorGravador(f"O teto é de 3 meses [{POLITICA_TETO}]."),
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
        falhar_citacoes=True,
    ).responder(PERGUNTA)

    [citacao] = resposta.citacoes
    assert (citacao.veredito, citacao.confianca) == ("incerta", None)
    assert resposta.resposta == (
        f"O teto é de 3 meses [{POLITICA_TETO} - não confirmada].\n\n{AVISO_SEM_VERIFICACAO}"
    )
    assert AVISO_SEM_VERIFICACAO == (
        "Observação: não consegui verificar as citações agora, então elas vêm marcadas como não confirmadas."
    )


def test_resposta_sem_llm_nao_passa_pela_verificacao() -> None:
    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorSemLLM(),
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
        falhar_citacoes=True,
    ).responder(PERGUNTA)

    assert resposta.redator == "sem_llm"
    assert resposta.citacoes == []
    assert "não confirmada" not in resposta.resposta
    assert AVISO_SEM_VERIFICACAO not in resposta.resposta


def test_queda_do_redator_nao_passa_pela_verificacao() -> None:
    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorGravador(nome="anthropic:modelo", falhar=True),
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
        falhar_citacoes=True,
    ).responder(PERGUNTA)

    assert resposta.redator == "sem_llm"
    assert resposta.citacoes == []


def test_faixa_media_verifica_so_a_redacao_depois_da_confirmacao() -> None:
    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.6),
        redator=RedatorGravador(f"O teto é de 3 meses [{POLITICA_TETO}]."),
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
    ).responder(PERGUNTA)

    assert resposta.resposta == (
        "Entendi que você quer saber da política de compra e dos fornecedores. "
        f"Se não for isso, reformule a pergunta.\n\nO teto é de 3 meses [{POLITICA_TETO} - não confirmada]."
    )
    [citacao] = resposta.citacoes
    assert citacao.afirmacao == "O teto é de 3 meses."


def test_registro_guarda_os_sinais_e_as_citacoes() -> None:
    registros = InMemoryRegistrosDecisao()

    resposta = copilot(
        make_entendimento("sugestao_compra", 0.95),
        redator=RedatorGravador(f"A Katrina atrasa [{LEAD_TIME}]."),
        trechos=[make_trecho(LEAD_TIME, "Katrina Têxtil atrasou")],
        avaliacoes={LEAD_TIME: ACEITO},
        sinais={LEAD_TIME: {"atraso_do_fornecedor": 0.97}},
        citacoes={LEAD_TIME: make_relacao("sustenta")},
        registros=registros,
    ).responder(SUGESTAO)

    [registro] = registros.listar(10)
    [sinais_do_sku] = registro.sinais
    assert sinais_do_sku.sku_code == "TBC-BEGE-70140-01"
    assert sinais_do_sku.sinais == resposta.sugestoes[0].sinais
    assert registro.citacoes == resposta.citacoes
    assert [c.veredito for c in registro.citacoes] == ["confirmada"]


def test_registro_distingue_sinais_calculados_sem_sinal_de_sinais_nao_calculados() -> None:
    def sinais_registrados(falhar_sinais: bool) -> list[SinaisDoSKU]:
        registros = InMemoryRegistrosDecisao()
        copilot(
            make_entendimento("sugestao_compra", 0.95),
            trechos=[make_trecho(LEAD_TIME)],
            avaliacoes={LEAD_TIME: ACEITO},
            falhar_sinais=falhar_sinais,
            registros=registros,
        ).responder(SUGESTAO)
        [registro] = registros.listar(10)
        return registro.sinais

    assert sinais_registrados(falhar_sinais=False) == [SinaisDoSKU(sku_code="TBC-BEGE-70140-01", sinais=[])]
    assert sinais_registrados(falhar_sinais=True) == [SinaisDoSKU(sku_code="TBC-BEGE-70140-01", sinais=None)]


def test_redacao_de_llm_sai_limpa_antes_da_verificacao_das_citacoes() -> None:
    redacao = f"O teto do TBC‑BEGE‑70140‑01 é de 3 meses 【{POLITICA_TETO}】."

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorGravador(redacao),
        trechos=[make_trecho(POLITICA_TETO)],
        avaliacoes={POLITICA_TETO: ACEITO},
        citacoes={POLITICA_TETO: make_relacao("sustenta")},
    ).responder(PERGUNTA)

    assert resposta.resposta == f"O teto do TBC-BEGE-70140-01 é de 3 meses [{POLITICA_TETO}]."
    [citacao] = resposta.citacoes
    assert (citacao.afirmacao, citacao.veredito) == ("O teto do TBC-BEGE-70140-01 é de 3 meses.", "confirmada")


def test_resposta_sem_llm_nao_passa_pela_limpeza() -> None:
    texto = "Teto do TBC‑BEGE de 3 meses 【nota】."

    resposta = copilot(
        make_entendimento("politica_ou_fornecedor", 0.95),
        redator=RedatorSemLLM(),
        trechos=[make_trecho(POLITICA_TETO, texto)],
        avaliacoes={POLITICA_TETO: ACEITO},
    ).responder(PERGUNTA)

    assert resposta.redator == "sem_llm"
    assert texto in resposta.resposta
