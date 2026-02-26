"""Tests for the EVI calculator module."""

import math
from datetime import date

import pytest

from evi_weights.calculator import (
    apply_constraints,
    apply_turnover_cap,
    combine_scores,
    compute_adjustment_factor,
    compute_baseline,
    compute_score,
    winsorize_score,
)
from evi_weights.models import RegionScore, ValuationSnapshot


class TestComputeBaseline:
    def _make_history(self, pe_values, start_year=2014):
        """Build quarterly history from a list of P/E values."""
        snaps = []
        year = start_year
        quarter = 0
        months = [3, 6, 9, 12]
        for val in pe_values:
            m = months[quarter % 4]
            d = 31 if m in (3, 12) else 30
            snaps.append(
                ValuationSnapshot(
                    date=date(year + quarter // 4, m, d),
                    pe_ratio=val,
                    pb_ratio=val * 0.15,
                )
            )
            quarter += 1
        return snaps

    def test_rolling_median(self):
        values = [15.0, 16.0, 17.0, 18.0, 14.0, 13.0, 19.0, 20.0] * 5
        history = self._make_history(values)
        effective = date(2024, 12, 31)
        result = compute_baseline(
            history, effective, "pe_ratio",
            method="rolling_median", lookback_years=15, min_history_years=5,
        )
        assert result is not None
        assert 13 < result < 20

    def test_rolling_mean(self):
        values = [10.0] * 20 + [20.0] * 20
        history = self._make_history(values)
        effective = date(2024, 12, 31)
        result = compute_baseline(
            history, effective, "pe_ratio",
            method="rolling_mean", lookback_years=15, min_history_years=5,
        )
        assert result is not None
        assert 14 < result < 16

    def test_insufficient_data_returns_none(self):
        values = [15.0, 16.0, 17.0]
        history = self._make_history(values, start_year=2023)
        effective = date(2024, 12, 31)
        result = compute_baseline(
            history, effective, "pe_ratio",
            method="rolling_median", lookback_years=10, min_history_years=5,
        )
        assert result is None

    def test_pb_ratio_baseline(self):
        values = [15.0, 16.0, 17.0, 18.0, 14.0, 13.0, 19.0, 20.0] * 5
        history = self._make_history(values)
        effective = date(2024, 12, 31)
        result = compute_baseline(
            history, effective, "pb_ratio",
            method="rolling_median", lookback_years=15, min_history_years=5,
        )
        assert result is not None
        assert result > 0


class TestComputeScore:
    def test_log_ratio_overvalued(self):
        score = compute_score(25.0, 20.0, method="log_ratio")
        assert score > 0
        assert abs(score - math.log(25.0 / 20.0)) < 1e-10

    def test_log_ratio_undervalued(self):
        score = compute_score(12.0, 18.0, method="log_ratio")
        assert score < 0

    def test_log_ratio_equal(self):
        score = compute_score(15.0, 15.0, method="log_ratio")
        assert abs(score) < 1e-10

    def test_zscore_method(self):
        score = compute_score(20.0, 15.0, method="zscore")
        assert abs(score - (20.0 - 15.0) / 15.0) < 1e-10

    def test_zero_baseline(self):
        score = compute_score(15.0, 0.0, method="log_ratio")
        assert score == 0.0

    def test_zero_current(self):
        score = compute_score(0.0, 15.0, method="log_ratio")
        assert score == 0.0


class TestWinsorize:
    def test_within_bounds(self):
        assert winsorize_score(0.5) == 0.5

    def test_clips_upper(self):
        assert winsorize_score(3.0, limits=(-2.5, 2.5)) == 2.5

    def test_clips_lower(self):
        assert winsorize_score(-3.0, limits=(-2.5, 2.5)) == -2.5

    def test_disabled(self):
        assert winsorize_score(5.0, enabled=False) == 5.0


class TestCombineScores:
    def test_both_present(self):
        result = combine_scores(0.2, -0.1, pe_weight=0.6, pb_weight=0.4)
        expected = 0.6 * 0.2 + 0.4 * (-0.1)
        assert abs(result - expected) < 1e-10

    def test_pe_only_reweight(self):
        result = combine_scores(0.3, None, missing_rule="reweight")
        assert result == 0.3

    def test_pb_only_reweight(self):
        result = combine_scores(None, -0.2, missing_rule="reweight")
        assert result == -0.2

    def test_both_missing_reweight(self):
        result = combine_scores(None, None, missing_rule="reweight")
        assert result == 0.0

    def test_drop_region_both_missing(self):
        result = combine_scores(None, None, missing_rule="drop_region")
        assert math.isnan(result)

    def test_drop_region_one_missing(self):
        result = combine_scores(0.3, None, missing_rule="drop_region")
        assert math.isnan(result)


class TestAdjustmentFactor:
    def test_exp_score_overvalued(self):
        factor = compute_adjustment_factor(0.5, function="exp_score", strength_k=0.8)
        assert factor < 1.0
        assert abs(factor - math.exp(-0.8 * 0.5)) < 1e-10

    def test_exp_score_undervalued(self):
        factor = compute_adjustment_factor(-0.3, function="exp_score", strength_k=0.8)
        assert factor > 1.0

    def test_exp_score_neutral(self):
        factor = compute_adjustment_factor(0.0, function="exp_score", strength_k=0.8)
        assert abs(factor - 1.0) < 1e-10

    def test_inverse_ratio(self):
        factor = compute_adjustment_factor(
            0.5, function="inverse_ratio", alpha=0.5, beta=0.5,
        )
        expected = 1.0 / (0.5 + 0.5 * math.exp(0.5))
        assert abs(factor - expected) < 1e-10

    def test_nan_score(self):
        factor = compute_adjustment_factor(float("nan"), function="exp_score")
        assert factor == 1.0


class TestApplyConstraints:
    def _make_scores(self, weights, mcap_weights):
        scores = []
        for i, (w, m) in enumerate(zip(weights, mcap_weights)):
            rs = RegionScore(name=f"Region{i}", mcap_weight=m)
            rs.final_weight = w
            scores.append(rs)
        return scores

    def test_floor_applied(self):
        scores = self._make_scores([0.005, 0.495, 0.5], [0.01, 0.49, 0.50])
        apply_constraints(scores, floor=0.02, ceiling=0.60,
                          max_overweight_pp=50, max_underweight_pp=-50)
        assert all(s.final_weight >= 0.02 for s in scores)
        assert abs(sum(s.final_weight for s in scores) - 1.0) < 1e-6

    def test_ceiling_applied(self):
        scores = self._make_scores([0.70, 0.20, 0.10], [0.65, 0.20, 0.15])
        apply_constraints(scores, floor=0.02, ceiling=0.60,
                          max_overweight_pp=50, max_underweight_pp=-50)
        assert all(s.final_weight <= 0.62 for s in scores)
        assert abs(sum(s.final_weight for s in scores) - 1.0) < 1e-6

    def test_weights_sum_to_one(self):
        scores = self._make_scores([0.3, 0.3, 0.2, 0.1, 0.05, 0.05],
                                   [0.3, 0.3, 0.2, 0.1, 0.05, 0.05])
        apply_constraints(scores, floor=0.02, ceiling=0.60,
                          max_overweight_pp=7.5, max_underweight_pp=-7.5)
        assert abs(sum(s.final_weight for s in scores) - 1.0) < 1e-6


class TestApplyTurnoverCap:
    def test_within_cap(self):
        scores = [
            RegionScore(name="A", mcap_weight=0.5),
            RegionScore(name="B", mcap_weight=0.5),
        ]
        scores[0].final_weight = 0.52
        scores[1].final_weight = 0.48
        prev = {"A": 0.50, "B": 0.50}
        apply_turnover_cap(scores, prev, turnover_cap_pp=10.0)
        assert abs(scores[0].final_weight - 0.52) < 1e-6

    def test_exceeds_cap(self):
        scores = [
            RegionScore(name="A", mcap_weight=0.5),
            RegionScore(name="B", mcap_weight=0.5),
        ]
        scores[0].final_weight = 0.60
        scores[1].final_weight = 0.40
        prev = {"A": 0.50, "B": 0.50}
        apply_turnover_cap(scores, prev, turnover_cap_pp=10.0)
        total_turnover = abs(scores[0].final_weight - 0.50) + abs(scores[1].final_weight - 0.50)
        assert total_turnover <= 0.11  # 10pp + floating point tolerance

    def test_no_previous_weights(self):
        scores = [RegionScore(name="A", mcap_weight=0.5)]
        scores[0].final_weight = 0.6
        apply_turnover_cap(scores, None, turnover_cap_pp=10.0)
        assert abs(scores[0].final_weight - 0.6) < 1e-6
