"""Faixa de aprovação de um pedido de compra (`politicas/aprovacao-compras.md` v2).

Os limites de valor são parâmetros da política de compra; as exceções do
documento são mecanismo. O documento avalia o valor com impostos e frete, que
o ERP fake não tem: a faixa usa o valor dos itens.
"""
from __future__ import annotations

from src.politica_compra.schemas import ParametrosPolitica
from src.purchasing.schemas import FaixaAprovacao


APROVADORES: dict[int, str] = {
    1: "comprador chefe",
    2: "comprador chefe + gerente comercial ou sócio financeiro",
    3: "comprador chefe + gerente comercial + sócio financeiro",
    4: "comprador chefe + gerente comercial + sócio financeiro, com reunião de compra registrada",
}

FAIXA_MINIMA_FORNECEDOR_SEM_PEDIDO = 3
FAIXA_MINIMA_COM_JUSTIFICATIVA = 2


def _faixa_pelo_valor(valor_centavos: int, parametros: ParametrosPolitica) -> int:
    limites = (parametros.faixa_1_ate_reais, parametros.faixa_2_ate_reais, parametros.faixa_3_ate_reais)
    return next(
        (faixa for faixa, ate_reais in enumerate(limites, start=1) if valor_centavos <= ate_reais * 100),
        4,
    )


def faixa_aprovacao(
    valor_centavos: int,
    *,
    viola_teto: bool,
    fornecedor_tem_pedido: bool,
    parametros: ParametrosPolitica,
) -> FaixaAprovacao:
    """Toda sugestão com quantidade é reposição de SKU com histórico (SKU novo
    não gera compra), então sem violação de teto a reposição regular vale sempre."""
    faixa = _faixa_pelo_valor(valor_centavos, parametros)
    ajustes: list[str] = []

    if viola_teto:
        nova = min(4, faixa + 1)
        motivo = "Viola o teto da política de estoque: sobe"
    else:
        nova = max(1, faixa - 1)
        motivo = "Reposição regular de SKU, dentro da política de estoque: desce"
    if nova != faixa:
        ajustes.append(f"{motivo} da faixa {faixa} para a {nova}.")
        faixa = nova

    if not fornecedor_tem_pedido and faixa < FAIXA_MINIMA_FORNECEDOR_SEM_PEDIDO:
        ajustes.append(
            f"Primeiro pedido com o fornecedor: no mínimo faixa {FAIXA_MINIMA_FORNECEDOR_SEM_PEDIDO}, "
            f"sobe da faixa {faixa} para a {FAIXA_MINIMA_FORNECEDOR_SEM_PEDIDO}."
        )
        faixa = FAIXA_MINIMA_FORNECEDOR_SEM_PEDIDO

    return FaixaAprovacao(
        faixa=faixa,
        aprovadores=APROVADORES[faixa],
        exige_justificativa=faixa >= FAIXA_MINIMA_COM_JUSTIFICATIVA,
        ajustes=ajustes,
    )
