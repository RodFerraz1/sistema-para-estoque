"""Testes do serviço `Aprovacao` com ERP, política, busca, modelo de decisão e fila em
memória.

Cenário: giro de 100 por mês em todos os SKUs, fornecedor Boa Vista com lead time de
30 dias, R$ 20,00 a unidade e MOQ 48. O consumo no lead time é de 100 unidades, então:

- `MEIO` (150 disponíveis) chega com 0,5 mês e compra 150; só tem os alertas de pedido
  mínimo e de época forte, que não destacam.
- `RUPTURA` (50 disponíveis) acaba antes da chegada (-0,5 mês) e compra 200.
- `QUASE` (120 disponíveis) chega com 0,2 mês e compra 180.
- `SOBRANDO` (900 disponíveis) não compra.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from src.ai.busca import BuscaContexto
from src.ai.in_memory import FakeEmbedder, InMemoryDecisionModel
from src.ai.schemas import AvaliacaoSinais, ProdutoDoSinal, SinaisDasSugestoes, SinalCorpus, Trecho
from src.ai.sinais import SinaisCorpus
from src.aprovacao.in_memory import InMemorySugestoesFila
from src.aprovacao.schemas import SugestaoNaFila
from src.aprovacao.service import (
    Aprovacao,
    JustificativaObrigatoria,
    SugestaoJaDecidida,
    SugestaoNaoEncontrada,
)
from src.catalog.schemas import SKU
from src.catalog.service import Catalog
from src.erp_adapter.in_memory import InMemoryERPAdapter
from src.ficha_sku.service import FichaSKU
from src.inventory.service import Inventory
from src.politica_compra.in_memory import InMemoryPoliticaCompraRepositorio
from src.purchasing.schemas import SugestaoPedido, TipoAlerta
from src.purchasing.service import Purchasing, QuantidadeInvalida
from src.sales.service import Sales
from tests.fakes import (
    make_estoque,
    make_fornecedor,
    make_fornecedor_sku,
    make_pedido_compra,
    make_sku,
    make_trecho,
    make_venda,
    repositorio_com,
)

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
BOA_VISTA = make_fornecedor("Boa Vista Têxtil", lead_time_dias_contratado=30)
MEIO = make_sku("TBC-BEGE-70140-01", produto_nome="Toalha Banho Conforto")
RUPTURA = make_sku("TBC-BRAN-70140-01", produto_nome="Toalha Banho Conforto")
QUASE = make_sku("TBC-CINZ-70140-01", produto_nome="Toalha Banho Conforto")
SOBRANDO = make_sku("TBC-AZUL-70140-01", produto_nome="Toalha Banho Conforto")
DISPONIVEIS = {MEIO: 150, RUPTURA: 50, QUASE: 120, SOBRANDO: 900}
ATRASO = "reunioes/revisao.md#boa-vista"
ACEITO = {"relevante": 0.9, "tem_evidencia": 0.9}


class SinaisFixos(SinaisCorpus):
    """Devolve os sinais configurados por SKU e guarda os pares de cada chamada."""

    def __init__(self, por_sku: dict[str, list[SinalCorpus]] | None = None) -> None:
        self._por_sku = por_sku or {}
        self.chamadas: list[list[tuple[str, str]]] = []

    def para_sugestoes(self, pares: Sequence[tuple[SugestaoPedido, SKU]]) -> SinaisDasSugestoes:
        self.chamadas.append([(s.sku_code, sku.sku_code) for s, sku in pares])
        return SinaisDasSugestoes(
            por_sku={s.sku_code: self._por_sku.get(s.sku_code, []) for s, _ in pares}, trechos_de_origem=[]
        )


class DecisaoEspia(InMemoryDecisionModel):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.chamadas_sinais: list[tuple[str, str]] = []

    def avaliar_sinais(
        self, fornecedor: str, produto: ProdutoDoSinal, trechos: Sequence[Trecho]
    ) -> list[AvaliacaoSinais]:
        self.chamadas_sinais.append((fornecedor, produto.nome))
        return super().avaliar_sinais(fornecedor, produto, trechos)


def sinais_do_corpus(decisao: InMemoryDecisionModel) -> SinaisCorpus:
    embedder = FakeEmbedder()
    trechos = repositorio_com([make_trecho(ATRASO, "Boa Vista atrasou as entregas")], embedder)
    return SinaisCorpus(BuscaContexto(embedder, trechos, decisao), decisao)


SINAL_DE_ATRASO = SinalCorpus(
    tipo="atraso_do_fornecedor",
    mensagem="Os documentos relatam atraso de entrega da Boa Vista Têxtil.",
    trechos=[ATRASO],
    probabilidade=0.97,
)


@dataclass
class Cenario:
    aprovacao: Aprovacao
    purchasing: Purchasing
    erp: InMemoryERPAdapter
    fila: InMemorySugestoesFila


def montar(
    disponiveis: dict[SKU, int] | None = None,
    *,
    com_pedido_anterior: bool = True,
    agora: datetime = NOW,
) -> Cenario:
    disponiveis = disponiveis or DISPONIVEIS
    erp = InMemoryERPAdapter(
        skus=list(disponiveis),
        fornecedores=[BOA_VISTA],
        fornecedores_por_sku={
            sku.sku_code: [make_fornecedor_sku(BOA_VISTA, preco_unitario_reais=2000, lead_time_dias_observado=30)]
            for sku in disponiveis
        },
        estoques={sku.sku_code: make_estoque(disponivel=d) for sku, d in disponiveis.items()},
        vendas=[
            make_venda(sku, datetime(2026, mes, 5, tzinfo=UTC), 100, key=f"{sku.sku_code}-{mes}")
            for sku in disponiveis
            for mes in range(3, 9)
        ],
        pedidos_compra=[make_pedido_compra(BOA_VISTA, "recebido_total")] if com_pedido_anterior else [],
    )
    sales = Sales(erp, now=agora)
    inventory = Inventory(erp, sales)
    catalog = Catalog(erp)
    purchasing = Purchasing(
        FichaSKU(catalog, inventory, sales), inventory, sales, InMemoryPoliticaCompraRepositorio(), erp, now=agora
    )
    fila = InMemorySugestoesFila()
    return Cenario(Aprovacao(catalog, purchasing, fila, now=agora), purchasing, erp, fila)


def gerada(cenario: Cenario, sinais: SinaisCorpus | None = None) -> list[SugestaoNaFila]:
    cenario.aprovacao.gerar_fila(sinais or SinaisFixos())
    return cenario.aprovacao.listar()


def da_fila(cenario: Cenario, sku: SKU) -> SugestaoNaFila:
    return next(s for s in cenario.aprovacao.listar() if s.sku_code == sku.sku_code)


# Geração


def test_gerar_guarda_so_as_sugestoes_com_compra() -> None:
    cenario = montar()

    resultado = cenario.aprovacao.gerar_fila(SinaisFixos())

    assert resultado.geradas == 3
    assert resultado.substituidas == 0
    assert resultado.skus_avaliados == 4
    assert resultado.sinais_indisponiveis is False
    fila = cenario.aprovacao.listar()
    assert {s.sku_code for s in fila} == {MEIO.sku_code, RUPTURA.sku_code, QUASE.sku_code}
    assert all(s.status == "pendente" and s.decidido_em is None for s in fila)
    assert {s.sku_code: s.sugestao.sugestao.quantidade for s in fila} == {
        MEIO.sku_code: 150,
        RUPTURA.sku_code: 200,
        QUASE.sku_code: 180,
    }


def test_sugestao_na_fila_leva_o_sku_a_faixa_e_os_sinais() -> None:
    cenario = montar()

    gerada(cenario, SinaisFixos({MEIO.sku_code: [SINAL_DE_ATRASO]}))

    meio = da_fila(cenario, MEIO)
    assert meio.sku == MEIO
    assert meio.sugestao.sinais == [SINAL_DE_ATRASO]
    assert meio.faixa == cenario.purchasing.faixa_aprovacao(meio.sugestao.sugestao)
    assert meio.faixa.faixa == 1
    assert da_fila(cenario, QUASE).sugestao.sinais == []


def test_sinais_sao_calculados_numa_chamada_com_todas_as_sugestoes_com_compra() -> None:
    cenario = montar()
    sinais = SinaisFixos()

    cenario.aprovacao.gerar_fila(sinais)

    assert sinais.chamadas == [
        [(s.sku_code, s.sku_code) for s in (MEIO, RUPTURA, QUASE)],
    ]


def test_sinais_do_corpus_sao_avaliados_uma_vez_por_par_fornecedor_e_produto() -> None:
    cenario = montar()
    decisao = DecisaoEspia(padrao=ACEITO, sinais={ATRASO: {"atraso_do_fornecedor": 0.97}})

    fila = gerada(cenario, sinais_do_corpus(decisao))

    assert decisao.chamadas_sinais == [("Boa Vista Têxtil", "Toalha Banho Conforto")]
    assert all(s.sugestao.sinais == [SINAL_DE_ATRASO] for s in fila)


def test_modelo_de_decisao_fora_do_ar_gera_a_fila_sem_sinais() -> None:
    cenario = montar()

    resultado = cenario.aprovacao.gerar_fila(
        sinais_do_corpus(InMemoryDecisionModel(padrao=ACEITO, falhar_sinais=True))
    )

    assert resultado.geradas == 3
    assert resultado.sinais_indisponiveis is True
    assert all(s.sugestao.sinais is None for s in cenario.aprovacao.listar())


def test_gerar_de_novo_substitui_as_pendentes_anteriores() -> None:
    cenario = montar()
    antigas = gerada(cenario)

    resultado = cenario.aprovacao.gerar_fila(SinaisFixos())

    assert resultado.substituidas == 3
    novas = cenario.aprovacao.listar()
    assert len(novas) == 3
    assert {s.id for s in novas}.isdisjoint({s.id for s in antigas})
    assert {s.id for s in cenario.aprovacao.listar("substituida")} == {s.id for s in antigas}


def test_gerar_de_novo_nao_mexe_nas_decididas() -> None:
    cenario = montar()
    gerada(cenario)
    rejeitada = cenario.aprovacao.rejeitar(da_fila(cenario, QUASE).id, "Ana", "Vamos trocar o fornecedor.")

    resultado = cenario.aprovacao.gerar_fila(SinaisFixos())

    assert resultado.substituidas == 2
    assert cenario.aprovacao.carregar(rejeitada.id) == rejeitada


def test_sku_aprovado_sai_da_fila_na_geracao_seguinte_porque_o_pedido_esta_em_transito() -> None:
    cenario = montar()
    gerada(cenario)
    cenario.aprovacao.aprovar(da_fila(cenario, MEIO).id, "Ana")

    fila = gerada(cenario)

    assert MEIO.sku_code not in {s.sku_code for s in fila}


# Destaque e ordem


def test_alerta_de_risco_destaca() -> None:
    cenario = montar()

    gerada(cenario)

    ruptura = da_fila(cenario, RUPTURA)
    assert TipoAlerta.RUPTURA_ANTES_DA_CHEGADA in {a.tipo for a in ruptura.sugestao.sugestao.alertas}
    assert ruptura.destaque is True


def test_pedido_minimo_e_epoca_forte_nao_destacam() -> None:
    cenario = montar()

    gerada(cenario)

    meio = da_fila(cenario, MEIO)
    assert {a.tipo for a in meio.sugestao.sugestao.alertas} == {
        TipoAlerta.ABAIXO_PEDIDO_MINIMO,
        TipoAlerta.PERIODO_SAZONAL,
    }
    assert meio.destaque is False


def test_sinal_do_corpus_destaca() -> None:
    cenario = montar()

    gerada(cenario, SinaisFixos({MEIO.sku_code: [SINAL_DE_ATRASO]}))

    assert da_fila(cenario, MEIO).destaque is True
    assert da_fila(cenario, QUASE).destaque is False


def test_ordem_da_fila_destaque_primeiro_e_depois_a_mais_urgente() -> None:
    cenario = montar()

    fila = gerada(cenario, SinaisFixos({MEIO.sku_code: [SINAL_DE_ATRASO]}))

    assert [(s.sku_code, s.destaque, s.cobertura_na_chegada_sem_compra_meses) for s in fila] == [
        (RUPTURA.sku_code, True, pytest.approx(-0.5)),
        (MEIO.sku_code, True, pytest.approx(0.5)),
        (QUASE.sku_code, False, pytest.approx(0.2)),
    ]


# Aprovação


def test_aprovar_com_a_quantidade_sugerida_cria_o_pedido_no_erp() -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)

    aprovada = cenario.aprovacao.aprovar(meio.id, "  Ana  ")

    assert aprovada.status == "aprovada"
    assert aprovada.decidido_em == NOW
    assert aprovada.decidido_por == "Ana"
    assert aprovada.quantidade_aprovada == 150
    assert aprovada.justificativa is None
    [pedido] = [p for p in cenario.erp.pedidos_compra if p.status == "aprovado"]
    assert aprovada.pedido_compra_id == pedido.id
    assert pedido.fornecedor_id == BOA_VISTA.id
    assert pedido.data_prevista_entrega == date(2026, 10, 15)
    assert pedido.observacao == f"Criado pelo Copilot a partir da sugestão {meio.id}, aprovado por Ana."
    [item] = [i for i in cenario.erp.itens_pedido_compra if i.pedido_id == pedido.id]
    assert (item.sku_id, item.quantidade, item.preco_unitario_centavos) == (MEIO.id, 150, 2000)
    assert cenario.aprovacao.carregar(meio.id) == aprovada
    assert meio.id not in {s.id for s in cenario.aprovacao.listar()}
    assert cenario.aprovacao.listar("aprovada") == [aprovada]


def test_aprovar_com_quantidade_editada_cria_o_pedido_com_ela() -> None:
    cenario = montar()
    gerada(cenario)

    aprovada = cenario.aprovacao.aprovar(da_fila(cenario, MEIO).id, "Ana", quantidade=96)

    assert aprovada.quantidade_aprovada == 96
    [item] = cenario.erp.itens_pedido_compra
    assert item.quantidade == 96


def test_aprovar_com_quantidade_editada_recalcula_a_faixa() -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)
    assert meio.faixa.faixa == 1

    # 400 unidades (R$ 8.000,00) levam a cobertura na chegada a 4,5 meses, acima do teto
    # de 3: em vez de descer como reposição regular, sobe da faixa 1 para a 2.
    aprovada = cenario.aprovacao.aprovar(meio.id, "Ana", quantidade=400, justificativa="Compra de oportunidade.")

    assert aprovada.faixa == cenario.purchasing.faixa_aprovacao(meio.sugestao.sugestao, 400)
    assert aprovada.faixa.faixa == 2
    assert aprovada.justificativa == "Compra de oportunidade."


def test_faixa_que_exige_justificativa_sem_justificativa_nao_cria_pedido() -> None:
    cenario = montar(com_pedido_anterior=False)
    gerada(cenario)
    meio = da_fila(cenario, MEIO)
    assert meio.faixa.faixa == 3

    with pytest.raises(JustificativaObrigatoria, match="faixa 3"):
        cenario.aprovacao.aprovar(meio.id, "Ana", justificativa="   ")

    assert cenario.erp.pedidos_compra == []
    assert cenario.aprovacao.carregar(meio.id) == meio


def test_faixa_que_exige_justificativa_com_justificativa_aprova() -> None:
    cenario = montar(com_pedido_anterior=False)
    gerada(cenario)

    aprovada = cenario.aprovacao.aprovar(
        da_fila(cenario, MEIO).id, "Ana", justificativa=" Fornecedor novo homologado. "
    )

    assert aprovada.status == "aprovada"
    assert aprovada.justificativa == "Fornecedor novo homologado."
    assert aprovada.faixa.faixa == 3


def test_justificativa_e_validada_com_a_faixa_recalculada() -> None:
    cenario = montar()
    gerada(cenario)

    with pytest.raises(JustificativaObrigatoria, match="faixa 2"):
        cenario.aprovacao.aprovar(da_fila(cenario, MEIO).id, "Ana", quantidade=400)

    assert cenario.erp.itens_pedido_compra == []


@pytest.mark.parametrize("quantidade", [0, -5, 47])
def test_quantidade_zero_ou_abaixo_do_moq_nao_cria_pedido(quantidade: int) -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)

    with pytest.raises(QuantidadeInvalida):
        cenario.aprovacao.aprovar(meio.id, "Ana", quantidade=quantidade)

    assert cenario.erp.itens_pedido_compra == []
    assert cenario.aprovacao.carregar(meio.id) == meio


def test_aprovar_sem_nome_nao_cria_pedido() -> None:
    cenario = montar()
    gerada(cenario)

    with pytest.raises(ValueError, match="aprovado_por"):
        cenario.aprovacao.aprovar(da_fila(cenario, MEIO).id, "  ")

    assert cenario.erp.itens_pedido_compra == []


def test_aprovar_sugestao_ja_decidida_falha_sem_criar_outro_pedido() -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)
    cenario.aprovacao.aprovar(meio.id, "Ana")

    with pytest.raises(SugestaoJaDecidida, match="aprovada"):
        cenario.aprovacao.aprovar(meio.id, "Bruno")

    assert len(cenario.erp.itens_pedido_compra) == 1


def test_aprovar_sugestao_substituida_falha() -> None:
    cenario = montar()
    antiga = gerada(cenario)[0]
    gerada(cenario)

    with pytest.raises(SugestaoJaDecidida, match="substituida"):
        cenario.aprovacao.aprovar(antiga.id, "Ana")


def test_aprovar_sugestao_inexistente_falha() -> None:
    with pytest.raises(SugestaoNaoEncontrada):
        montar().aprovacao.aprovar(uuid4(), "Ana")


# Rejeição


def test_rejeitar_registra_o_motivo_sem_criar_pedido() -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)

    rejeitada = cenario.aprovacao.rejeitar(meio.id, " Ana ", " Vamos esperar a feira. ")

    assert rejeitada.status == "rejeitada"
    assert rejeitada.decidido_por == "Ana"
    assert rejeitada.decidido_em == NOW
    assert rejeitada.motivo_rejeicao == "Vamos esperar a feira."
    assert rejeitada.pedido_compra_id is None
    assert rejeitada.quantidade_aprovada is None
    assert cenario.erp.itens_pedido_compra == []
    assert cenario.aprovacao.listar("rejeitada") == [rejeitada]


@pytest.mark.parametrize(("rejeitado_por", "motivo", "campo"), [("Ana", "  ", "motivo"), ("", "Caro", "rejeitado_por")])
def test_rejeitar_exige_nome_e_motivo(rejeitado_por: str, motivo: str, campo: str) -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)

    with pytest.raises(ValueError, match=campo):
        cenario.aprovacao.rejeitar(meio.id, rejeitado_por, motivo)

    assert cenario.aprovacao.carregar(meio.id) == meio


def test_rejeitar_sugestao_ja_decidida_falha() -> None:
    cenario = montar()
    gerada(cenario)
    meio = da_fila(cenario, MEIO)
    cenario.aprovacao.aprovar(meio.id, "Ana")

    with pytest.raises(SugestaoJaDecidida):
        cenario.aprovacao.rejeitar(meio.id, "Bruno", "Mudei de ideia.")


def test_rejeitar_sugestao_inexistente_falha() -> None:
    with pytest.raises(SugestaoNaoEncontrada):
        montar().aprovacao.rejeitar(uuid4(), "Ana", "Motivo.")

