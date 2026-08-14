from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.asset_dir.mkdir(parents=True, exist_ok=True)
settings.tmp_dir.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
engine = create_engine(settings.resolved_database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


SCHEMA_VERSION = 2


def _apply_schema_migrations() -> None:
    """Apply additive SQLite-safe migrations after creating new tables.

    ``create_all`` is sufficient for a new local database but intentionally does
    not add columns to an existing one. The migration ledger keeps upgrades
    explicit and makes future additive changes reviewable.
    """
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        current = connection.exec_driver_sql("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").scalar_one()
        if current >= SCHEMA_VERSION:
            return

        columns = {
            table: {column["name"] for column in sqlalchemy_inspect(connection).get_columns(table)}
            for table in ("projects", "scenes", "scene_nodes", "ai_tasks")
        }
        if current < 1:
            for table in ("projects", "scenes", "scene_nodes"):
                if "version" not in columns[table]:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            connection.exec_driver_sql(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
                (1,),
            )
            current = 1
        if current < 2:
            if "cancel_requested" not in columns["ai_tasks"]:
                connection.exec_driver_sql("ALTER TABLE ai_tasks ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT 0")
            connection.exec_driver_sql(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
                (2,),
            )


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_schema_migrations()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
