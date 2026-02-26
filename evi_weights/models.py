"""Data models for EVI weight calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class ValuationSnapshot:
    """A single point-in-time valuation reading for a region."""

    date: date
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    earnings_growth: Optional[float] = None


@dataclass
class RegionData:
    """Complete data for a single region including current and historical values."""

    name: str
    index_proxy: str
    etf_ticker: str
    mcap_weight: float
    current: ValuationSnapshot
    history: list[ValuationSnapshot] = field(default_factory=list)


@dataclass
class RegionScore:
    """Intermediate scoring results for a region."""

    name: str
    mcap_weight: float
    pe_score: Optional[float] = None
    pb_score: Optional[float] = None
    composite_score: float = 0.0
    adjustment_factor: float = 1.0
    raw_evi_weight: float = 0.0
    normalized_weight: float = 0.0
    shrunk_weight: float = 0.0
    final_weight: float = 0.0

    # Diagnostic fields
    current_pe: Optional[float] = None
    current_pb: Optional[float] = None
    baseline_pe: Optional[float] = None
    baseline_pb: Optional[float] = None

    @property
    def weight_delta_pp(self) -> float:
        """Difference from mcap weight in percentage points."""
        return (self.final_weight - self.mcap_weight) * 100


@dataclass
class EVIResult:
    """Full output of an EVI calculation run."""

    as_of_date: date
    effective_date: date
    region_scores: list[RegionScore]

    @property
    def total_weight(self) -> float:
        return sum(rs.final_weight for rs in self.region_scores)

    def to_dict(self) -> list[dict]:
        rows = []
        for rs in self.region_scores:
            rows.append(
                {
                    "Region": rs.name,
                    "MCAP Weight": rs.mcap_weight,
                    "Current P/E": rs.current_pe,
                    "Baseline P/E": rs.baseline_pe,
                    "P/E Score": rs.pe_score,
                    "Current P/B": rs.current_pb,
                    "Baseline P/B": rs.baseline_pb,
                    "P/B Score": rs.pb_score,
                    "Composite Score": rs.composite_score,
                    "Adjustment Factor": rs.adjustment_factor,
                    "EVI Weight": rs.final_weight,
                    "Delta (pp)": rs.weight_delta_pp,
                }
            )
        return rows
