from fastapi import APIRouter, Depends, Response, status

from src.db.health import check_database

router = APIRouter()


@router.get("/health")
def health(response: Response, db_ok: bool = Depends(check_database)) -> dict[str, str]:
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "db": "unreachable"}
    return {"status": "ok", "db": "ok"}
