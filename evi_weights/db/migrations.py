"""Schema bootstrap — create all tables."""

from evi_weights.db.models import Base


def create_all(engine) -> None:
    Base.metadata.create_all(engine)
