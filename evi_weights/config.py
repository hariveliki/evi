"""Configuration loading and validation for EVI calculation parameters."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class WinsorizeConfig:
    enabled: bool = True
    method: str = "clip"
    limits: tuple[float, float] = (-2.5, 2.5)


@dataclass
class ScoringConfig:
    score_method: str = "log_ratio"
    winsorize: WinsorizeConfig = field(default_factory=WinsorizeConfig)


@dataclass
class BaselineConfig:
    baseline_method: str = "rolling_median"
    lookback_years: int = 10
    min_history_years: int = 5


@dataclass
class ValuationInputsConfig:
    pe_type: str = "trailing_12m"
    pb_type: str = "latest"
    earnings_growth_type: Optional[str] = None


@dataclass
class CombineMetricsConfig:
    metric_weights: dict[str, float] = field(
        default_factory=lambda: {"pe": 0.6, "pb": 0.4}
    )
    missing_metric_rule: str = "reweight"


@dataclass
class AdjustmentConfig:
    function: str = "exp_score"
    strength_k: float = 0.8
    alpha: float = 0.5
    beta: float = 0.5


@dataclass
class ConstraintsConfig:
    weight_floor: float = 0.02
    weight_ceiling: float = 0.60
    max_overweight_pp: float = 7.5
    max_underweight_pp: float = -7.5
    shrinkage_to_mcap_lambda: float = 0.20
    turnover_cap_pp: Optional[float] = 10.0


@dataclass
class RegionConfig:
    name: str
    index_proxy: str
    etf_ticker: str


@dataclass
class EVIConfig:
    as_of_date: date = field(default_factory=date.today)
    rebalance_frequency: str = "quarterly"
    data_lag_days: int = 5

    valuation_inputs: ValuationInputsConfig = field(
        default_factory=ValuationInputsConfig
    )
    baseline: BaselineConfig = field(default_factory=BaselineConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    combine_metrics: CombineMetricsConfig = field(
        default_factory=CombineMetricsConfig
    )
    adjustment: AdjustmentConfig = field(default_factory=AdjustmentConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    regions: list[RegionConfig] = field(default_factory=list)

    @property
    def effective_date(self) -> date:
        """As-of date minus data lag."""
        return self.as_of_date - timedelta(days=self.data_lag_days)


def _parse_winsorize(raw: dict) -> WinsorizeConfig:
    limits = raw.get("limits", [-2.5, 2.5])
    return WinsorizeConfig(
        enabled=raw.get("enabled", True),
        method=raw.get("method", "clip"),
        limits=(float(limits[0]), float(limits[1])),
    )


def _parse_scoring(raw: dict) -> ScoringConfig:
    return ScoringConfig(
        score_method=raw.get("score_method", "log_ratio"),
        winsorize=_parse_winsorize(raw.get("winsorize", {})),
    )


def _parse_regions(raw_list: list[dict]) -> list[RegionConfig]:
    return [
        RegionConfig(
            name=r["name"],
            index_proxy=r["index_proxy"],
            etf_ticker=r["etf_ticker"],
        )
        for r in raw_list
    ]


def load_config(path: str | Path | None = None) -> EVIConfig:
    """Load configuration from a YAML file.

    Falls back to default config.yaml in the project root if no path given.
    """
    if path is None:
        path = Path(__file__).parent.parent / "config.yaml"
    else:
        path = Path(path)

    with open(path) as f:
        raw = yaml.safe_load(f)

    params = raw.get("calculation_parameters", {})

    as_of_raw = params.get("as_of_date")
    if as_of_raw:
        as_of_date = date.fromisoformat(str(as_of_raw))
    else:
        as_of_date = date.today()

    vi = params.get("valuation_inputs", {})
    bl = params.get("baseline", {})
    sc = params.get("scoring", {})
    cm = params.get("combine_metrics", {})
    adj = params.get("adjustment", {})
    con = params.get("constraints", {})
    regions_raw = raw.get("regions", [])

    return EVIConfig(
        as_of_date=as_of_date,
        rebalance_frequency=params.get("rebalance_frequency", "quarterly"),
        data_lag_days=params.get("data_lag_days", 5),
        valuation_inputs=ValuationInputsConfig(
            pe_type=vi.get("pe_type", "trailing_12m"),
            pb_type=vi.get("pb_type", "latest"),
            earnings_growth_type=vi.get("earnings_growth_type"),
        ),
        baseline=BaselineConfig(
            baseline_method=bl.get("baseline_method", "rolling_median"),
            lookback_years=bl.get("lookback_years", 10),
            min_history_years=bl.get("min_history_years", 5),
        ),
        scoring=_parse_scoring(sc),
        combine_metrics=CombineMetricsConfig(
            metric_weights=cm.get("metric_weights", {"pe": 0.6, "pb": 0.4}),
            missing_metric_rule=cm.get("missing_metric_rule", "reweight"),
        ),
        adjustment=AdjustmentConfig(
            function=adj.get("function", "exp_score"),
            strength_k=adj.get("strength_k", 0.8),
            alpha=adj.get("alpha", 0.5),
            beta=adj.get("beta", 0.5),
        ),
        constraints=ConstraintsConfig(
            weight_floor=con.get("weight_floor", 0.02),
            weight_ceiling=con.get("weight_ceiling", 0.60),
            max_overweight_pp=con.get("max_overweight_pp", 7.5),
            max_underweight_pp=con.get("max_underweight_pp", -7.5),
            shrinkage_to_mcap_lambda=con.get("shrinkage_to_mcap_lambda", 0.20),
            turnover_cap_pp=con.get("turnover_cap_pp", 10.0),
        ),
        regions=_parse_regions(regions_raw),
    )
