"""Export endpoints."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_db
from evi_weights.db.repository import Repository

router = APIRouter(tags=["export"])


def _run_to_dicts(run) -> list[dict]:
    return [
        {
            "region_name": rr.region_name,
            "mcap_weight": rr.mcap_weight,
            "current_pe": rr.current_pe,
            "current_pb": rr.current_pb,
            "baseline_pe": rr.baseline_pe,
            "baseline_pb": rr.baseline_pb,
            "pe_score": rr.pe_score,
            "pb_score": rr.pb_score,
            "composite_score": rr.composite_score,
            "adjustment_factor": rr.adjustment_factor,
            "raw_evi_weight": rr.raw_evi_weight,
            "normalized_weight": rr.normalized_weight,
            "shrunk_weight": rr.shrunk_weight,
            "final_weight": rr.final_weight,
        }
        for rr in run.region_results
    ]


@router.get("/export/csv")
def export_csv(run_id: int = Query(...), db: Session = Depends(get_db)):
    repo = Repository(db)
    run = repo.load_calculation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    rows = _run_to_dicts(run)
    if not rows:
        raise HTTPException(status_code=404, detail="No results for run")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=evi_run_{run_id}.csv"},
    )


@router.get("/export/json")
def export_json(run_id: int = Query(...), db: Session = Depends(get_db)):
    repo = Repository(db)
    run = repo.load_calculation_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    data = {
        "run_id": run.id,
        "as_of_date": run.as_of_date.isoformat(),
        "effective_date": run.effective_date.isoformat(),
        "config": json.loads(run.config.config_json),
        "regions": _run_to_dicts(run),
    }
    return data
