"""Pydantic request/response models for the EVI API."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# -- Request models ---------------------------------------------------------

class ConfigOverrides(BaseModel):
    strength_k: Optional[float] = None
    shrinkage_lambda: Optional[float] = None
    pe_weight: Optional[float] = None
    pb_weight: Optional[float] = None
    weight_floor: Optional[float] = None
    weight_ceiling: Optional[float] = None
    max_overweight_pp: Optional[float] = None
    max_underweight_pp: Optional[float] = None
    score_method: Optional[str] = None
    baseline_method: Optional[str] = None
    lookback_years: Optional[int] = None
    adjustment_function: Optional[str] = None


class CalculateRequest(BaseModel):
    source: str = "sample"
    config_overrides: Optional[ConfigOverrides] = None
    scenario_name: Optional[str] = None


class RecalculateRequest(BaseModel):
    run_id: int
    config_overrides: Optional[ConfigOverrides] = None


class ScenarioVariant(BaseModel):
    label: str
    config_overrides: ConfigOverrides


class ScenarioCompareRequest(BaseModel):
    name: str
    source: str = "sample"
    variants: list[ScenarioVariant]


class BacktestRequest(BaseModel):
    start_date: date = Field(default_factory=lambda: date(2016, 1, 1))
    end_date: date = Field(default_factory=lambda: date(2025, 12, 31))
    frequency: str = "quarterly"
    config_overrides: Optional[ConfigOverrides] = None
    source: str = "sample"


# -- Response models --------------------------------------------------------

class RegionResultResponse(BaseModel):
    region_name: str
    mcap_weight: float
    current_pe: Optional[float] = None
    current_pb: Optional[float] = None
    baseline_pe: Optional[float] = None
    baseline_pb: Optional[float] = None
    pe_score: Optional[float] = None
    pb_score: Optional[float] = None
    composite_score: float
    adjustment_factor: float
    raw_evi_weight: float
    normalized_weight: float
    shrunk_weight: float
    final_weight: float


class CalculateResponse(BaseModel):
    run_id: int
    as_of_date: date
    effective_date: date
    total_weight: float
    regions: list[RegionResultResponse]
    config_used: dict


class RunSummaryResponse(BaseModel):
    id: int
    as_of_date: date
    effective_date: date
    scenario_name: Optional[str] = None
    triggered_by: str
    created_at: str
    region_count: int


class RunDetailResponse(BaseModel):
    id: int
    as_of_date: date
    effective_date: date
    scenario_name: Optional[str] = None
    triggered_by: str
    created_at: str
    config: dict
    regions: list[RegionResultResponse]


class RegionInfo(BaseModel):
    name: str
    latest_date: Optional[date] = None
    snapshot_count: int


class SnapshotResponse(BaseModel):
    date: date
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    earnings_growth: Optional[float] = None


class RegionHistoryResponse(BaseModel):
    region_name: str
    snapshots: list[SnapshotResponse]


class BacktestPoint(BaseModel):
    as_of_date: date
    run_id: int
    regions: list[dict]


class BacktestResponse(BaseModel):
    points: list[BacktestPoint]


class ScenarioCompareResponse(BaseModel):
    scenario_id: int
    name: str
    variants: list[dict]
