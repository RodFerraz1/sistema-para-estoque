from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.ai.decisao import DecisaoIndisponivel
from src.api.aprovacao import router as aprovacao_router
from src.api.chat import router as chat_router
from src.api.health import router as health_router
from src.api.politica_compra import router as politica_compra_router
from src.api.rag import decisao_indisponivel
from src.api.rag import router as rag_router
from src.api.skus import router as skus_router

UI_DIR = Path(__file__).parent / "ui"


def create_app() -> FastAPI:
    app = FastAPI(title="Copilot de Compras", version="0.1.0")
    app.include_router(health_router)
    app.include_router(skus_router)
    app.include_router(politica_compra_router)
    app.include_router(rag_router)
    app.include_router(chat_router)
    app.include_router(aprovacao_router)
    # Handler no app, e não no endpoint, porque a dependência do Jev também lança sem JEV_KEY.
    app.add_exception_handler(DecisaoIndisponivel, decisao_indisponivel)
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def raiz() -> RedirectResponse:
        return RedirectResponse("/ui/")

    return app


app = create_app()
