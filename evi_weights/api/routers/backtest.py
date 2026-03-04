"""Backtest endpoints."""

from __future__ import annotations

import copy
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_config, get_db
from evi_weights.api.routers.calculate import _apply_overrides
from evi_weights.api.schemas import BacktestRequest, BacktestResponse, BacktestPoint
from evi_weights.calculator import calculate_evi_weights
from evi_weights.config import EVIConfig
from evi_weights.data_provider import generate_sample_data
from evi_weights.db.repository import Repository
from evi_weights.models import RegionData, ValuationSnapshot

router = APIRouter(tags=["backtest"])


def _quarter_dates(start: date, end: date) -> list[date]:
    """Generate quarter-end dates in range."""
    dates = []
    for year in range(start.year, end.year + 1):
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            d = date(year, month, day)
            if start <= d <= end:
                dates.append(d)
    return dates


def _slice_data_at_date(
    full_data: list[RegionData], as_of: date
) -> list[RegionData]:
    """Filter each region's history up to as_of and set current to latest."""
    sliced = []
    for rd in full_data:
        history = [s for s in rd.history if s.date <= as_of]
        if not history:
            continue
        current = history[-1]
        sliced.append(RegionData(
            name=rd.name,
            index_proxy=rd.index_proxy,
            etf_ticker=rd.etf_ticker,
            mcap_weight=rd.mcap_weight,
            current=current,
            history=history,
        ))
    return sliced


@router.post("/backtest", response_model=BacktestResponse)
def backtest(
    req: BacktestRequest,
    db: Session = Depends(get_db),
    base_config: EVIConfig = Depends(get_config),
):
    config = _apply_overrides(base_config, req.config_overrides)

    # Generate full sample data
    full_data = generate_sample_data(config)

    repo = Repository(db)
    dates = _quarter_dates(req.start_date, req.end_date)
    points = []

    for as_of in dates:
        cfg = copy.deepcopy(config)
        cfg.as_of_date = as_of

        sliced = _slice_data_at_date(full_data, as_of)
        if not sliced:
            continue

        result = calculate_evi_weights(cfg, sliced)
        if not result.region_scores:
            continue

        run = repo.save_calculation_run(cfg, result, triggered_by="backtest")
        points.append(BacktestPoint(
            as_of_date=as_of,
            run_id=run.id,
            regions=[
                {
                    "name": rs.name,
                    "mcap_weight": rs.mcap_weight,
                    "evi_weight": rs.final_weight,
                    "composite_score": rs.composite_score,
                }
                for rs in result.region_scores
            ],
        ))

    return BacktestResponse(points=points)
