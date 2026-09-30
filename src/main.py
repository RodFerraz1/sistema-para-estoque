from fastapi import FastAPI

from src.ai.decisao import DecisaoIndisponivel
from src.api.health import router as health_router
from src.api.politica_compra import router as politica_compra_router
from src.api.rag import decisao_indisponivel
from src.api.rag import router as rag_router
from src.api.skus import router as skus_router


def create_app() -> FastAPI:
    app = FastAPI(title="Copilot de Compras", version="0.1.0")
    app.include_router(health_router)
    app.include_router(skus_router)
    app.include_router(politica_compra_router)
    app.include_router(rag_router)
    # Handler no app, e não no endpoint, porque a dependência do Jev também lança sem JEV_KEY.
    app.add_exception_handler(DecisaoIndisponivel, decisao_indisponivel)
    return app


app = create_app()
