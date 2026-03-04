"""Region endpoints."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from evi_weights.api.dependencies import get_db
from evi_weights.api.schemas import RegionHistoryResponse, RegionInfo, SnapshotResponse
from evi_weights.db.repository import Repository

router = APIRouter(tags=["regions"])


@router.get("/regions", response_model=list[RegionInfo])
def list_regions(db: Session = Depends(get_db)):
    repo = Repository(db)
    return [
        RegionInfo(
            name=r["name"],
            latest_date=r["latest_date"],
            snapshot_count=r["snapshot_count"],
        )
        for r in repo.list_regions()
    ]


@router.get("/regions/{name}/history", response_model=RegionHistoryResponse)
def region_history(
    name: str,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    source: str = Query("sample"),
    db: Session = Depends(get_db),
):
    repo = Repository(db)
    rows = repo.load_snapshots(name, source=source, start_date=start_date, end_date=end_date)
    return RegionHistoryResponse(
        region_name=name,
        snapshots=[
            SnapshotResponse(
                date=r.snapshot_date,
                pe_ratio=r.pe_ratio,
                pb_ratio=r.pb_ratio,
                earnings_growth=r.earnings_growth,
            )
            for r in rows
        ],
    )
