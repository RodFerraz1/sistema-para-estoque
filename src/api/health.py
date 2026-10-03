from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from src.db.health import check_database

router = APIRouter()

BANCO_INDISPONIVEL = (
    "O banco de dados está fora do ar: o Copilot não consegue ler o ERP agora. "
    "É um problema de infraestrutura, não do estoque."
)


def banco_indisponivel(request: Request, erro: Exception) -> JSONResponse:
    """Handler de `OperationalError` do SQLAlchemy: sem conexão com o Postgres, 503 com
    mensagem, como o health, em vez de 500."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": BANCO_INDISPONIVEL}
    )


@router.get("/health")
def health(response: Response, db_ok: bool = Depends(check_database)) -> dict[str, str]:
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "db": "unreachable"}
    return {"status": "ok", "db": "ok"}
