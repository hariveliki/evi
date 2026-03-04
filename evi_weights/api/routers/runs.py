"""Calculation run endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_db
from evi_weights.api.schemas import (
    RegionResultResponse,
    RunDetailResponse,
    RunSummaryResponse,
)
from evi_weights.db.repository import Repository

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunSummaryResponse])
def list_runs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    repo = Repository(db)
    runs = repo.list_runs(limit=limit, offset=offset)
    return [
        RunSummaryResponse(
            id=r.id,
            as_of_date=r.as_of_date,
            effective_date=r.effective_date,
            scenario_name=r.scenario_name,
            triggered_by=r.triggered_by,
            created_at=r.created_at.isoformat(),
            region_count=len(r.region_results),
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    repo = Repository(db)
    run = repo.load_calculation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunDetailResponse(
        id=run.id,
        as_of_date=run.as_of_date,
        effective_date=run.effective_date,
        scenario_name=run.scenario_name,
        triggered_by=run.triggered_by,
        created_at=run.created_at.isoformat(),
        config=json.loads(run.config.config_json),
        regions=[
            RegionResultResponse(
                region_name=rr.region_name,
                mcap_weight=rr.mcap_weight,
                current_pe=rr.current_pe,
                current_pb=rr.current_pb,
                baseline_pe=rr.baseline_pe,
                baseline_pb=rr.baseline_pb,
                pe_score=rr.pe_score,
                pb_score=rr.pb_score,
                composite_score=rr.composite_score,
                adjustment_factor=rr.adjustment_factor,
                raw_evi_weight=rr.raw_evi_weight,
                normalized_weight=rr.normalized_weight,
                shrunk_weight=rr.shrunk_weight,
                final_weight=rr.final_weight,
            )
            for rr in run.region_results
        ],
    )
