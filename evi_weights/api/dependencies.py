"""FastAPI dependency injection."""

from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from evi_weights.config import EVIConfig, load_config
from evi_weights.db.engine import get_engine, get_session_factory
from evi_weights.db.migrations import create_all

_engine = None
_session_factory = None
_config: EVIConfig | None = None


def init_db(db_url: str | None = None) -> None:
    global _engine, _session_factory
    _engine = get_engine(db_url)
    create_all(_engine)
    _session_factory = get_session_factory(_engine)


def get_db() -> Generator[Session, None, None]:
    if _session_factory is None:
        init_db()
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_config() -> EVIConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: EVIConfig) -> None:
    global _config
    _config = config


def override_session_factory(factory) -> None:
    """For testing: override the session factory."""
    global _session_factory
    _session_factory = factory
