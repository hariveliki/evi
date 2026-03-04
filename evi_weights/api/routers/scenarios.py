"""Scenario comparison endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_config, get_db
from evi_weights.api.routers.calculate import _apply_overrides
from evi_weights.api.schemas import ScenarioCompareRequest, ScenarioCompareResponse
from evi_weights.calculator import calculate_evi_weights
from evi_weights.config import EVIConfig
from evi_weights.data_provider import get_region_data
from evi_weights.db.repository import Repository, _config_to_json

router = APIRouter(tags=["scenarios"])


@router.post("/scenarios/compare", response_model=ScenarioCompareResponse)
def compare_scenarios(
    req: ScenarioCompareRequest,
    db: Session = Depends(get_db),
    base_config: EVIConfig = Depends(get_config),
):
    # Fetch data once, share across variants
    region_data = get_region_data(base_config, source=req.source)
    repo = Repository(db)
    repo.save_snapshots(region_data, source=req.source)

    run_labels = []
    variants_out = []

    for variant in req.variants:
        cfg = _apply_overrides(base_config, variant.config_overrides)
        result = calculate_evi_weights(cfg, region_data)
        run = repo.save_calculation_run(
            cfg, result, scenario_name=req.name, triggered_by="api"
        )
        run_labels.append((run, variant.label))
        variants_out.append({
            "label": variant.label,
            "run_id": run.id,
            "config_overrides": variant.config_overrides.model_dump(exclude_none=True),
            "regions": [
                {
                    "region_name": rs.name,
                    "mcap_weight": rs.mcap_weight,
                    "final_weight": rs.final_weight,
                    "composite_score": rs.composite_score,
                    "adjustment_factor": rs.adjustment_factor,
                }
                for rs in result.region_scores
            ],
        })

    scenario = repo.save_scenario(name=req.name, run_labels=run_labels)
    return ScenarioCompareResponse(
        scenario_id=scenario.id,
        name=req.name,
        variants=variants_out,
    )
