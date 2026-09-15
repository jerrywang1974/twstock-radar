from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    """Add newly introduced columns on existing SQLite files."""
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    alters = {
        "ai_insights": [
            ("risk_level", "VARCHAR(16) DEFAULT 'medium'"),
            ("growth_score", "FLOAT"),
            ("upside_pct", "FLOAT"),
            ("downside_pct", "FLOAT"),
            ("avoid_reason", "TEXT DEFAULT ''"),
            ("growth_thesis", "TEXT DEFAULT ''"),
        ]
    }
    with engine.begin() as conn:
        for table, cols in alters.items():
            existing = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            if not existing:
                continue
            for name, ddl in cols:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
