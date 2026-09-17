from sqlalchemy import text

from src.db.engine import get_engine


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
