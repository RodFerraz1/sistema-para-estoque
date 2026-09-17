from fastapi.testclient import TestClient

from src.db.health import check_database
from src.main import app


def test_health_ok_when_db_reachable():
    app.dependency_overrides[check_database] = lambda: True
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "db": "ok"}
    finally:
        app.dependency_overrides.pop(check_database, None)


def test_health_degraded_when_db_unreachable():
    app.dependency_overrides[check_database] = lambda: False
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "degraded", "db": "unreachable"}
    finally:
        app.dependency_overrides.pop(check_database, None)
