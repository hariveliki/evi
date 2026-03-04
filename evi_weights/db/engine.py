"""SQLAlchemy engine and session factory."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_DEFAULT_URL = "sqlite:///data/evi.db"


def get_engine(url: str | None = None):
    url = url or os.environ.get("EVI_DB_URL", _DEFAULT_URL)
    return create_engine(url, echo=False)


def get_session_factory(engine=None):
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)
