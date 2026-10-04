"""Endpoints HTTP das notificações: o sino de qualquer pessoa logada."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.schemas import NotificacaoResponse, NotificacoesResponse
from src.notificacoes.dependencies import get_notificacoes
from src.notificacoes.service import Notificacoes
from src.painel.dependencies import get_painel
from src.painel.service import Painel
from src.usuarios.dependencies import usuario_atual
from src.usuarios.schemas import Usuario

router = APIRouter(tags=["notificacoes"])


@router.get("/notificacoes", response_model=NotificacoesResponse)
def notificacoes(
    usuario: Usuario = Depends(usuario_atual),
    notificacoes: Notificacoes = Depends(get_notificacoes),
    painel: Painel = Depends(get_painel),
) -> NotificacoesResponse:
    """Varre antes as condições dos papéis do usuário (ruptura e entrega atrasada para o
    comprador) e devolve as notificações desses papéis, as mais recentes primeiro (no
    máximo 50), com o total de não lidas. 503 com o banco fora do ar."""
    if "comprador" in usuario.papeis:
        painel.varrer_episodios()
    caixa = notificacoes.caixa(usuario)
    return NotificacoesResponse(
        notificacoes=[
            NotificacaoResponse(
                id=n.episodio.id,
                tipo=n.episodio.tipo,
                sku_code=n.episodio.sku_code,
                pedido_id=n.episodio.pedido_id,
                aberto_em=n.episodio.aberto_em,
                fechado_em=n.episodio.fechado_em,
                detalhe=n.episodio.detalhe,
                lida=n.lida,
            )
            for n in caixa.notificacoes
        ],
        nao_lidas=caixa.nao_lidas,
    )


@router.post("/notificacoes/vistas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_vistas(
    usuario: Usuario = Depends(usuario_atual), notificacoes: Notificacoes = Depends(get_notificacoes)
) -> None:
    """Marca como lidas todas as notificações abertas até agora."""
    notificacoes.marcar_vistas(usuario)
