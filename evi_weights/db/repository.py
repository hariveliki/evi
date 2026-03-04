"""CRUD operations for EVI database."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from evi_weights.config import EVIConfig
from evi_weights.db.models import (
    CalculationConfigRow,
    CalculationRunRow,
    McapWeightRow,
    RegionResultRow,
    ScenarioRow,
    ScenarioRunRow,
    ValuationSnapshotRow,
)
from evi_weights.models import EVIResult, RegionData, RegionScore


def _config_to_json(config: EVIConfig) -> str:
    """Serialize config to a stable JSON string."""
    d = {
        "as_of_date": config.as_of_date.isoformat(),
        "rebalance_frequency": config.rebalance_frequency,
        "data_lag_days": config.data_lag_days,
        "baseline": {
            "baseline_method": config.baseline.baseline_method,
            "lookback_years": config.baseline.lookback_years,
            "min_history_years": config.baseline.min_history_years,
        },
        "scoring": {
            "score_method": config.scoring.score_method,
            "winsorize": {
                "enabled": config.scoring.winsorize.enabled,
                "method": config.scoring.winsorize.method,
                "limits": list(config.scoring.winsorize.limits),
            },
        },
        "combine_metrics": {
            "metric_weights": config.combine_metrics.metric_weights,
            "missing_metric_rule": config.combine_metrics.missing_metric_rule,
        },
        "adjustment": {
            "function": config.adjustment.function,
            "strength_k": config.adjustment.strength_k,
            "alpha": config.adjustment.alpha,
            "beta": config.adjustment.beta,
        },
        "constraints": {
            "weight_floor": config.constraints.weight_floor,
            "weight_ceiling": config.constraints.weight_ceiling,
            "max_overweight_pp": config.constraints.max_overweight_pp,
            "max_underweight_pp": config.constraints.max_underweight_pp,
            "shrinkage_to_mcap_lambda": config.constraints.shrinkage_to_mcap_lambda,
            "turnover_cap_pp": config.constraints.turnover_cap_pp,
        },
    }
    return json.dumps(d, sort_keys=True)


def _config_hash(config_json: str) -> str:
    return hashlib.sha256(config_json.encode()).hexdigest()


class Repository:
    def __init__(self, session: Session):
        self.session = session

    # -- Snapshots ----------------------------------------------------------

    def save_snapshots(
        self, regions: list[RegionData], source: str = "sample"
    ) -> int:
        """Save valuation snapshots and mcap weights. Returns count of new rows."""
        count = 0
        for rd in regions:
            # Save mcap weight
            existing_mcap = (
                self.session.query(McapWeightRow)
                .filter_by(
                    region_name=rd.name,
                    as_of_date=rd.current.date,
                    source=source,
                )
                .first()
            )
            if not existing_mcap:
                self.session.add(McapWeightRow(
                    region_name=rd.name,
                    as_of_date=rd.current.date,
                    mcap_weight=rd.mcap_weight,
                    source=source,
                ))

            # Save current + history snapshots
            for snap in rd.history:
                existing = (
                    self.session.query(ValuationSnapshotRow)
                    .filter_by(
                        region_name=rd.name,
                        snapshot_date=snap.date,
                        source=source,
                    )
                    .first()
                )
                if not existing:
                    self.session.add(ValuationSnapshotRow(
                        region_name=rd.name,
                        etf_ticker=rd.etf_ticker,
                        snapshot_date=snap.date,
                        pe_ratio=snap.pe_ratio,
                        pb_ratio=snap.pb_ratio,
                        earnings_growth=snap.earnings_growth,
                        source=source,
                    ))
                    count += 1
        self.session.flush()
        return count

    def load_snapshots(
        self, region_name: str, source: str = "sample",
        start_date: Optional[date] = None, end_date: Optional[date] = None,
    ) -> list[ValuationSnapshotRow]:
        q = self.session.query(ValuationSnapshotRow).filter_by(
            region_name=region_name, source=source
        )
        if start_date:
            q = q.filter(ValuationSnapshotRow.snapshot_date >= start_date)
        if end_date:
            q = q.filter(ValuationSnapshotRow.snapshot_date <= end_date)
        return q.order_by(ValuationSnapshotRow.snapshot_date).all()

    # -- Config -------------------------------------------------------------

    def save_config(self, config: EVIConfig) -> CalculationConfigRow:
        config_json = _config_to_json(config)
        h = _config_hash(config_json)
        existing = (
            self.session.query(CalculationConfigRow)
            .filter_by(config_hash=h)
            .first()
        )
        if existing:
            return existing
        row = CalculationConfigRow(config_json=config_json, config_hash=h)
        self.session.add(row)
        self.session.flush()
        return row

    # -- Calculation runs ---------------------------------------------------

    def save_calculation_run(
        self,
        config: EVIConfig,
        result: EVIResult,
        scenario_name: Optional[str] = None,
        triggered_by: str = "api",
    ) -> CalculationRunRow:
        config_row = self.save_config(config)
        run = CalculationRunRow(
            as_of_date=result.as_of_date,
            effective_date=result.effective_date,
            config_id=config_row.id,
            scenario_name=scenario_name,
            triggered_by=triggered_by,
        )
        self.session.add(run)
        self.session.flush()

        for rs in result.region_scores:
            self.session.add(RegionResultRow(
                run_id=run.id,
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
            ))
        self.session.flush()
        return run

    def load_calculation_run(self, run_id: int) -> Optional[CalculationRunRow]:
        return (
            self.session.query(CalculationRunRow)
            .filter_by(id=run_id)
            .first()
        )

    def list_runs(
        self, limit: int = 50, offset: int = 0
    ) -> list[CalculationRunRow]:
        return (
            self.session.query(CalculationRunRow)
            .order_by(CalculationRunRow.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    # -- Scenarios ----------------------------------------------------------

    def save_scenario(
        self,
        name: str,
        run_labels: list[tuple[CalculationRunRow, str]],
        description: Optional[str] = None,
    ) -> ScenarioRow:
        scenario = ScenarioRow(name=name, description=description)
        self.session.add(scenario)
        self.session.flush()
        for run, label in run_labels:
            self.session.add(ScenarioRunRow(
                scenario_id=scenario.id,
                run_id=run.id,
                label=label,
            ))
        self.session.flush()
        return scenario

    def load_scenario(self, scenario_id: int) -> Optional[ScenarioRow]:
        return (
            self.session.query(ScenarioRow)
            .filter_by(id=scenario_id)
            .first()
        )

    def list_regions(self) -> list[dict]:
        """Get distinct regions with latest snapshot info."""
        from sqlalchemy import func
        rows = (
            self.session.query(
                ValuationSnapshotRow.region_name,
                func.max(ValuationSnapshotRow.snapshot_date).label("latest_date"),
                func.count(ValuationSnapshotRow.id).label("snapshot_count"),
            )
            .group_by(ValuationSnapshotRow.region_name)
            .all()
        )
        return [
            {
                "name": r.region_name,
                "latest_date": r.latest_date,
                "snapshot_count": r.snapshot_count,
            }
            for r in rows
        ]
