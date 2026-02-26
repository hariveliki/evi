"""Core EVI weight calculation engine.

Implements the full pipeline:
1. Compute baselines (rolling median/mean of historical valuations)
2. Score each region's current valuation vs baseline
3. Winsorize scores
4. Combine P/E and P/B scores into composite
5. Compute adjustment factors
6. Apply adjustment to market cap weights
7. Normalize, shrink toward mcap, apply constraints
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

import numpy as np

from evi_weights.config import EVIConfig
from evi_weights.models import (
    EVIResult,
    RegionData,
    RegionScore,
    ValuationSnapshot,
)


def compute_baseline(
    history: list[ValuationSnapshot],
    effective_date: date,
    metric: str,
    method: str = "rolling_median",
    lookback_years: int = 10,
    min_history_years: int = 5,
) -> Optional[float]:
    """Compute the baseline value for a metric over the lookback window.

    Args:
        history: Historical valuation snapshots (sorted by date).
        effective_date: The reference date for the calculation.
        metric: "pe_ratio" or "pb_ratio".
        method: "rolling_median", "rolling_mean", or "fixed".
        lookback_years: Number of years to look back.
        min_history_years: Minimum years of data required.

    Returns:
        The baseline value, or None if insufficient data.
    """
    cutoff = date(
        effective_date.year - lookback_years,
        effective_date.month,
        effective_date.day,
    )
    min_cutoff = date(
        effective_date.year - min_history_years,
        effective_date.month,
        effective_date.day,
    )

    values = []
    for snap in history:
        if snap.date < cutoff or snap.date > effective_date:
            continue
        val = getattr(snap, metric, None)
        if val is not None and val > 0:
            values.append(val)

    min_points = max(4, min_history_years * 4)
    earliest_data = min((s.date for s in history if getattr(s, metric, None)), default=None)
    if earliest_data and earliest_data > min_cutoff:
        return None
    if len(values) < min_points:
        return None

    if method == "rolling_median":
        return float(np.median(values))
    elif method == "rolling_mean":
        return float(np.mean(values))
    elif method == "fixed":
        return values[0] if values else None
    else:
        raise ValueError(f"Unknown baseline method: {method}")


def compute_score(
    current: float,
    baseline: float,
    method: str = "log_ratio",
) -> float:
    """Compute valuation score comparing current to baseline.

    Positive score = overvalued (current > baseline).
    Negative score = undervalued (current < baseline).
    """
    if baseline <= 0 or current <= 0:
        return 0.0

    if method == "log_ratio":
        return math.log(current / baseline)
    elif method == "zscore":
        return (current - baseline) / baseline
    elif method == "percentile":
        return (current - baseline) / baseline
    else:
        raise ValueError(f"Unknown score method: {method}")


def winsorize_score(
    score: float,
    enabled: bool = True,
    limits: tuple[float, float] = (-2.5, 2.5),
) -> float:
    """Clip score to the given bounds."""
    if not enabled:
        return score
    return max(limits[0], min(limits[1], score))


def combine_scores(
    pe_score: Optional[float],
    pb_score: Optional[float],
    pe_weight: float = 0.6,
    pb_weight: float = 0.4,
    missing_rule: str = "reweight",
) -> float:
    """Combine P/E and P/B scores into a composite score.

    Args:
        missing_rule: How to handle missing metrics.
            "reweight" - redistribute weight to available metrics.
            "drop_region" - return NaN to signal this region should be dropped.
            "fallback_pb_only" - use P/B only if P/E missing, or vice versa.
    """
    has_pe = pe_score is not None
    has_pb = pb_score is not None

    if has_pe and has_pb:
        return pe_weight * pe_score + pb_weight * pb_score

    if not has_pe and not has_pb:
        if missing_rule == "drop_region":
            return float("nan")
        return 0.0

    if missing_rule == "reweight":
        return pe_score if has_pe else pb_score  # type: ignore[return-value]
    elif missing_rule == "drop_region":
        return float("nan")
    elif missing_rule == "fallback_pb_only":
        return pb_score if has_pb else (pe_score if has_pe else 0.0)  # type: ignore[return-value]
    else:
        return pe_score if has_pe else pb_score  # type: ignore[return-value]


def compute_adjustment_factor(
    composite_score: float,
    function: str = "exp_score",
    strength_k: float = 0.8,
    alpha: float = 0.5,
    beta: float = 0.5,
) -> float:
    """Compute the weight adjustment factor from the composite score.

    For exp_score: factor = exp(-k * score)
        Overvalued (score > 0) → factor < 1 → reduce weight
        Undervalued (score < 0) → factor > 1 → increase weight

    For inverse_ratio: factor = 1 / (alpha + beta * exp(score))
    """
    if math.isnan(composite_score):
        return 1.0

    if function == "exp_score":
        return math.exp(-strength_k * composite_score)
    elif function == "inverse_ratio":
        return 1.0 / (alpha + beta * math.exp(composite_score))
    else:
        raise ValueError(f"Unknown adjustment function: {function}")


def apply_constraints(
    scores: list[RegionScore],
    floor: float,
    ceiling: float,
    max_overweight_pp: float,
    max_underweight_pp: float,
    max_iterations: int = 50,
) -> None:
    """Apply weight floor, ceiling, and over/underweight constraints in-place.

    Uses an iterative clip-and-redistribute approach: frozen weights that hit
    a bound are locked, and the remaining budget is redistributed proportionally
    among unfrozen regions until all constraints are satisfied.

    Absolute floor/ceiling take priority over relative over/underweight limits.
    """
    n = len(scores)
    if n == 0:
        return

    for _ in range(max_iterations):
        frozen = [False] * n
        changed = False

        for i, rs in enumerate(scores):
            lo = max(floor, rs.mcap_weight + max_underweight_pp / 100.0)
            hi = min(ceiling, rs.mcap_weight + max_overweight_pp / 100.0)
            lo = min(lo, ceiling)
            hi = max(hi, floor)

            old_w = rs.final_weight
            w = max(lo, min(hi, rs.final_weight))

            if abs(w - lo) < 1e-12 or abs(w - hi) < 1e-12:
                frozen[i] = True

            if abs(w - old_w) > 1e-10:
                changed = True
            rs.final_weight = w

        frozen_sum = sum(
            scores[i].final_weight for i in range(n) if frozen[i]
        )
        free_sum = sum(
            scores[i].final_weight for i in range(n) if not frozen[i]
        )
        target_free = 1.0 - frozen_sum

        if free_sum > 1e-12 and target_free > 0:
            scale = target_free / free_sum
            for i in range(n):
                if not frozen[i]:
                    scores[i].final_weight *= scale
        elif target_free <= 0:
            for i in range(n):
                if not frozen[i]:
                    scores[i].final_weight = 0.0

        total = sum(rs.final_weight for rs in scores)
        if abs(total - 1.0) < 1e-10 and not changed:
            break

    total = sum(rs.final_weight for rs in scores)
    if total > 0 and abs(total - 1.0) > 1e-10:
        for rs in scores:
            rs.final_weight /= total


def apply_turnover_cap(
    scores: list[RegionScore],
    previous_weights: Optional[dict[str, float]],
    turnover_cap_pp: float,
) -> None:
    """Limit total turnover (sum of absolute changes) to the cap.

    Scales changes proportionally if turnover exceeds the cap.
    """
    if previous_weights is None:
        return

    total_turnover = 0.0
    deltas: dict[str, float] = {}
    for rs in scores:
        prev = previous_weights.get(rs.name, rs.mcap_weight)
        delta = rs.final_weight - prev
        deltas[rs.name] = delta
        total_turnover += abs(delta)

    cap = turnover_cap_pp / 100.0
    if total_turnover <= cap:
        return

    scale = cap / total_turnover
    for rs in scores:
        prev = previous_weights.get(rs.name, rs.mcap_weight)
        rs.final_weight = prev + deltas[rs.name] * scale

    total = sum(rs.final_weight for rs in scores)
    if total > 0:
        for rs in scores:
            rs.final_weight /= total


def calculate_evi_weights(
    config: EVIConfig,
    region_data: list[RegionData],
    previous_weights: Optional[dict[str, float]] = None,
) -> EVIResult:
    """Execute the full EVI weight calculation pipeline.

    Args:
        config: Calculation parameters.
        region_data: List of region data with current and historical valuations.
        previous_weights: Optional previous period weights for turnover cap.

    Returns:
        EVIResult with final weights and diagnostics.
    """
    effective = config.effective_date
    scores: list[RegionScore] = []

    for rd in region_data:
        rs = RegionScore(name=rd.name, mcap_weight=rd.mcap_weight)
        rs.current_pe = rd.current.pe_ratio
        rs.current_pb = rd.current.pb_ratio

        # Step 1: Compute baselines
        baseline_pe = compute_baseline(
            rd.history,
            effective,
            "pe_ratio",
            method=config.baseline.baseline_method,
            lookback_years=config.baseline.lookback_years,
            min_history_years=config.baseline.min_history_years,
        )
        baseline_pb = compute_baseline(
            rd.history,
            effective,
            "pb_ratio",
            method=config.baseline.baseline_method,
            lookback_years=config.baseline.lookback_years,
            min_history_years=config.baseline.min_history_years,
        )
        rs.baseline_pe = baseline_pe
        rs.baseline_pb = baseline_pb

        # Step 2: Score
        pe_score = None
        if rd.current.pe_ratio and baseline_pe:
            pe_score = compute_score(
                rd.current.pe_ratio,
                baseline_pe,
                method=config.scoring.score_method,
            )
            pe_score = winsorize_score(
                pe_score,
                enabled=config.scoring.winsorize.enabled,
                limits=config.scoring.winsorize.limits,
            )
        rs.pe_score = pe_score

        pb_score = None
        if rd.current.pb_ratio and baseline_pb:
            pb_score = compute_score(
                rd.current.pb_ratio,
                baseline_pb,
                method=config.scoring.score_method,
            )
            pb_score = winsorize_score(
                pb_score,
                enabled=config.scoring.winsorize.enabled,
                limits=config.scoring.winsorize.limits,
            )
        rs.pb_score = pb_score

        # Step 3: Combine
        weights = config.combine_metrics.metric_weights
        rs.composite_score = combine_scores(
            pe_score,
            pb_score,
            pe_weight=weights.get("pe", 0.6),
            pb_weight=weights.get("pb", 0.4),
            missing_rule=config.combine_metrics.missing_metric_rule,
        )

        # Step 4: Adjustment factor
        rs.adjustment_factor = compute_adjustment_factor(
            rs.composite_score,
            function=config.adjustment.function,
            strength_k=config.adjustment.strength_k,
            alpha=config.adjustment.alpha,
            beta=config.adjustment.beta,
        )

        # Step 5: Raw EVI weight
        rs.raw_evi_weight = rd.mcap_weight * rs.adjustment_factor

        scores.append(rs)

    # Drop regions with NaN composite score if drop_region rule was used
    scores = [s for s in scores if not math.isnan(s.composite_score)]

    if not scores:
        return EVIResult(
            as_of_date=config.as_of_date,
            effective_date=effective,
            region_scores=[],
        )

    # Step 6: Normalize
    raw_total = sum(s.raw_evi_weight for s in scores)
    for s in scores:
        s.normalized_weight = s.raw_evi_weight / raw_total if raw_total > 0 else 0.0

    # Step 7: Shrinkage toward market cap
    lam = config.constraints.shrinkage_to_mcap_lambda
    for s in scores:
        s.shrunk_weight = (1 - lam) * s.normalized_weight + lam * s.mcap_weight

    shrunk_total = sum(s.shrunk_weight for s in scores)
    for s in scores:
        s.final_weight = s.shrunk_weight / shrunk_total if shrunk_total > 0 else 0.0

    # Step 8: Apply constraints
    apply_constraints(
        scores,
        floor=config.constraints.weight_floor,
        ceiling=config.constraints.weight_ceiling,
        max_overweight_pp=config.constraints.max_overweight_pp,
        max_underweight_pp=config.constraints.max_underweight_pp,
    )

    # Step 9: Apply turnover cap
    if config.constraints.turnover_cap_pp is not None:
        apply_turnover_cap(scores, previous_weights, config.constraints.turnover_cap_pp)

    return EVIResult(
        as_of_date=config.as_of_date,
        effective_date=effective,
        region_scores=scores,
    )
