"""Calculate endpoints."""

from __future__ import annotations

import copy
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_config, get_db
from evi_weights.api.schemas import (
    CalculateRequest,
    CalculateResponse,
    ConfigOverrides,
    RecalculateRequest,
    RegionResultResponse,
)
from evi_weights.calculator import calculate_evi_weights
from evi_weights.config import EVIConfig
from evi_weights.data_provider import get_region_data
from evi_weights.db.repository import Repository, _config_to_json

router = APIRouter(tags=["calculate"])


def _apply_overrides(config: EVIConfig, overrides: ConfigOverrides | None) -> EVIConfig:
    """Return a new config with overrides applied."""
    cfg = copy.deepcopy(config)
    if overrides is None:
        return cfg
    if overrides.strength_k is not None:
        cfg.adjustment.strength_k = overrides.strength_k
    if overrides.shrinkage_lambda is not None:
        cfg.constraints.shrinkage_to_mcap_lambda = overrides.shrinkage_lambda
    if overrides.pe_weight is not None:
        cfg.combine_metrics.metric_weights["pe"] = overrides.pe_weight
        cfg.combine_metrics.metric_weights["pb"] = 1.0 - overrides.pe_weight
    if overrides.pb_weight is not None:
        cfg.combine_metrics.metric_weights["pb"] = overrides.pb_weight
        cfg.combine_metrics.metric_weights["pe"] = 1.0 - overrides.pb_weight
    if overrides.weight_floor is not None:
        cfg.constraints.weight_floor = overrides.weight_floor
    if overrides.weight_ceiling is not None:
        cfg.constraints.weight_ceiling = overrides.weight_ceiling
    if overrides.max_overweight_pp is not None:
        cfg.constraints.max_overweight_pp = overrides.max_overweight_pp
    if overrides.max_underweight_pp is not None:
        cfg.constraints.max_underweight_pp = overrides.max_underweight_pp
    if overrides.score_method is not None:
        cfg.scoring.score_method = overrides.score_method
    if overrides.baseline_method is not None:
        cfg.baseline.baseline_method = overrides.baseline_method
    if overrides.lookback_years is not None:
        cfg.baseline.lookback_years = overrides.lookback_years
    if overrides.adjustment_function is not None:
        cfg.adjustment.function = overrides.adjustment_function
    return cfg


def _build_response(run_id: int, result, config: EVIConfig) -> CalculateResponse:
    return CalculateResponse(
        run_id=run_id,
        as_of_date=result.as_of_date,
        effective_date=result.effective_date,
        total_weight=result.total_weight,
        regions=[
            RegionResultResponse(
                region_name=rs.name,
                mcap_weight=rs.mcap_weight,
                current_pe=rs.current_pe,
                current_pb=rs.current_pb,
                baseline_pe=rs.baseline_pe,
                baseline_pb=rs.baseline_pb,
                pe_score=rs.pe_score,
                pb_score=rs.pb_score,
                composite_score=rs.composite_score,
                adjustment_factor=rs.adjustment_factor,
                raw_evi_weight=rs.raw_evi_weight,
                normalized_weight=rs.normalized_weight,
                shrunk_weight=rs.shrunk_weight,
                final_weight=rs.final_weight,
            )
            for rs in result.region_scores
        ],
        config_used=json.loads(_config_to_json(config)),
    )


@router.post("/calculate", response_model=CalculateResponse)
def calculate(
    req: CalculateRequest,
    db: Session = Depends(get_db),
    base_config: EVIConfig = Depends(get_config),
):
    config = _apply_overrides(base_config, req.config_overrides)
    region_data = get_region_data(config, source=req.source)

    repo = Repository(db)
    repo.save_snapshots(region_data, source=req.source)

    result = calculate_evi_weights(config, region_data)
    run = repo.save_calculation_run(
        config, result, scenario_name=req.scenario_name, triggered_by="api"
    )
    return _build_response(run.id, result, config)


@router.post("/recalculate", response_model=CalculateResponse)
def recalculate(
    req: RecalculateRequest,
    db: Session = Depends(get_db),
    base_config: EVIConfig = Depends(get_config),
):
    repo = Repository(db)
    original_run = repo.load_calculation_run(req.run_id)
    if original_run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Run not found")

    config = _apply_overrides(base_config, req.config_overrides)
    region_data = get_region_data(config, source="sample")

    result = calculate_evi_weights(config, region_data)
    run = repo.save_calculation_run(config, result, triggered_by="api")
    return _build_response(run.id, result, config)
