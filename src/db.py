"""SQLAlchemy setup for the public Site Flask app.

Wired to the local ``site_db`` PostgreSQL database via peer auth on the
Unix socket. Same Base/declarative pattern as the private Whiteboard's
``src/db.py``, but a separate engine so models from the two apps don't
collide on a shared metadata.

Cross-app data flow: the chat agent (``agent`` PG role) and the Whiteboard
app (``console`` PG role) can connect to ``site_db`` and write content
there; this ``site`` process cannot reach ``console_db`` (REVOKE CONNECT
in setup).
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

log = logging.getLogger("site.db")

DATABASE_URL = "postgresql+psycopg2:///site_db?host=/var/run/postgresql"

# Multi-site: every site lives in its own Postgres schema inside site_db.
# Gunicorn's environment provides PG_SCHEMA (set by site-http-runner.sh from
# the systemd %i instance name). The `options=-csearch_path=...` query arg
# is honored by libpq on every new connection — both the standalone engine
# below and Flask-SQLAlchemy's internal engine pick it up via the URI.
PG_SCHEMA = os.environ.get("PG_SCHEMA", "default")
_search_path_opt = f"-csearch_path={PG_SCHEMA},public"
_db_uri = f"{DATABASE_URL}&options={_search_path_opt}"


class Base(DeclarativeBase):
    """Declarative base for every public-app model."""


db = SQLAlchemy(model_class=Base)

# Standalone engine for background-thread / CLI / job use via ``session_scope``
# (Flask-SQLAlchemy's ``db.session`` is request-scoped via the app context, so
# it raises outside a Flask request).
engine = create_engine(
    _db_uri,
    pool_pre_ping=True,
    pool_recycle=3600,
    future=True,
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, future=True)

# Thread-local scoped session — works inside a Flask request OR a background
# thread, where ``db.session`` would raise on missing app context. New code
# in routes should prefer ``db.session``.
db_session = scoped_session(SessionLocal)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Short-lived session for background work. Commits on success, rolls
    back on exception, always closes. Use ``db.session`` inside Flask routes."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db_app(app: Flask) -> None:
    """Wire Flask-SQLAlchemy into the Flask app. Call once from ``app.py``
    after every model module is imported."""
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", _db_uri)
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "future": True,
    })
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)

    @app.teardown_appcontext
    def _remove_session(_exc: BaseException | None) -> None:
        db_session.remove()

    with app.app_context():
        db.create_all()
    print(f"[site-db] create_all ok — {len(Base.metadata.tables)} tables registered")


__all__ = [
    "Base",
    "DATABASE_URL",
    "SessionLocal",
    "db",
    "db_session",
    "engine",
    "init_db_app",
    "session_scope",
]
