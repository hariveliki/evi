"""ORM models for EVI database tables."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ValuationSnapshotRow(Base):
    __tablename__ = "valuation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_name = Column(String, nullable=False)
    etf_ticker = Column(String, nullable=False)
    snapshot_date = Column(Date, nullable=False)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    earnings_growth = Column(Float)
    source = Column(String, nullable=False, default="sample")
    fetched_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("region_name", "snapshot_date", "source"),
    )


class McapWeightRow(Base):
    __tablename__ = "mcap_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region_name = Column(String, nullable=False)
    as_of_date = Column(Date, nullable=False)
    mcap_weight = Column(Float, nullable=False)
    source = Column(String, nullable=False, default="sample")

    __table_args__ = (
        UniqueConstraint("region_name", "as_of_date", "source"),
    )


class CalculationConfigRow(Base):
    __tablename__ = "calculation_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_json = Column(Text, nullable=False)
    config_hash = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))


class CalculationRunRow(Base):
    __tablename__ = "calculation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    as_of_date = Column(Date, nullable=False)
    effective_date = Column(Date, nullable=False)
    config_id = Column(Integer, ForeignKey("calculation_configs.id"), nullable=False)
    scenario_name = Column(String)
    triggered_by = Column(String, nullable=False, default="api")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    config = relationship("CalculationConfigRow")
    region_results = relationship(
        "RegionResultRow", back_populates="run", cascade="all, delete-orphan"
    )
    scenario_links = relationship(
        "ScenarioRunRow", back_populates="run", cascade="all, delete-orphan"
    )


class RegionResultRow(Base):
    __tablename__ = "region_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        Integer, ForeignKey("calculation_runs.id", ondelete="CASCADE"), nullable=False
    )
    region_name = Column(String, nullable=False)
    mcap_weight = Column(Float, nullable=False)
    current_pe = Column(Float)
    current_pb = Column(Float)
    baseline_pe = Column(Float)
    baseline_pb = Column(Float)
    pe_score = Column(Float)
    pb_score = Column(Float)
    composite_score = Column(Float, nullable=False)
    adjustment_factor = Column(Float, nullable=False)
    raw_evi_weight = Column(Float, nullable=False)
    normalized_weight = Column(Float, nullable=False)
    shrunk_weight = Column(Float, nullable=False)
    final_weight = Column(Float, nullable=False)

    run = relationship("CalculationRunRow", back_populates="region_results")

    __table_args__ = (UniqueConstraint("run_id", "region_name"),)


class ScenarioRow(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    runs = relationship(
        "ScenarioRunRow", back_populates="scenario", cascade="all, delete-orphan"
    )


class ScenarioRunRow(Base):
    __tablename__ = "scenario_runs"

    scenario_id = Column(
        Integer,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    run_id = Column(
        Integer,
        ForeignKey("calculation_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label = Column(String, nullable=False)

    scenario = relationship("ScenarioRow", back_populates="runs")
    run = relationship("CalculationRunRow", back_populates="scenario_links")
