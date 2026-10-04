from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import OperationalError
from starlette.responses import Response
from starlette.types import Scope

from src.ai.decisao import DecisaoIndisponivel
from src.api.catalogo import router as catalogo_router
from src.api.chat import router as chat_router
from src.api.entregas import router as entregas_router
from src.api.health import banco_indisponivel
from src.api.health import router as health_router
from src.api.notificacoes import router as notificacoes_router
from src.api.painel import router as painel_router
from src.api.politica_compra import router as politica_compra_router
from src.api.rag import decisao_indisponivel
from src.api.rag import router as rag_router
from src.api.reposicao import router as reposicao_router
from src.api.skus import router as skus_router
from src.api.skus import sku_sem_estoque
from src.api.usuarios import router as usuarios_router
from src.db.config import get_settings
from src.ficha_sku.service import SKUSemEstoque
from src.usuarios.dependencies import exige_x_requested_with

UI_DIR = Path(__file__).parent / "ui"


class UISemCache(StaticFiles):
    """Sem `Cache-Control`, o navegador reaproveita HTML, CSS e JS antigos por heurística e a
    UI não muda depois de um deploy. Com `no-cache` ele revalida sempre pelo ETag (304 sem mudança)."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app() -> FastAPI:
    # Lida na subida para a configuração inválida (REDATOR sem a chave do provedor) impedir o app de subir.
    get_settings()
    app = FastAPI(title="Copilot de Compras", version="0.1.0", dependencies=[Depends(exige_x_requested_with)])
    app.include_router(health_router)
    app.include_router(usuarios_router)
    app.include_router(skus_router)
    app.include_router(catalogo_router)
    app.include_router(politica_compra_router)
    app.include_router(rag_router)
    app.include_router(chat_router)
    app.include_router(painel_router)
    app.include_router(entregas_router)
    app.include_router(notificacoes_router)
    app.include_router(reposicao_router)
    # Handler no app, e não no endpoint, porque a dependência do Jev também lança sem JEV_KEY.
    app.add_exception_handler(DecisaoIndisponivel, decisao_indisponivel)
    app.add_exception_handler(SKUSemEstoque, sku_sem_estoque)
    app.add_exception_handler(OperationalError, banco_indisponivel)
    app.mount("/ui", UISemCache(directory=UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def raiz() -> RedirectResponse:
        return RedirectResponse("/ui/")

    return app


app = create_app()
