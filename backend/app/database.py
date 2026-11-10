"""SQLAlchemy engine, session, and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# PostgreSQL in production; SQLite supported in test isolation.
# pool_pre_ping recycles connections dropped by the server or a network blip.
if settings.database_url.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Verify the PostgreSQL connection, then ensure tables exist.

    Fails fast with an actionable message if the database is unreachable —
    previously a bad DATABASE_URL silently fell back to a local SQLite file.
    Schema changes should go through Alembic; create_all only fills in tables
    that don't exist yet and never alters existing ones.
    """
    from app import models  # noqa: F401  (register models on Base)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Cannot connect to PostgreSQL using DATABASE_URL "
            f"({_safe_url()}).\n"
            "Check that: the server is running and reachable on that host/port, "
            "the database exists (createdb soil_health), and the credentials are "
            f"correct.\nOriginal error: {exc.__class__.__name__}: {exc}"
        ) from exc

    Base.metadata.create_all(bind=engine)


def _safe_url() -> str:
    """Engine URL with the password masked, safe for logs and error messages."""
    return engine.url.render_as_string(hide_password=True)
