"""Mathematical property tests for the EVI calculation pipeline.

Verifies algebraic invariants, monotonicity, and edge-case behavior
of the core calculator functions.
"""

import math
from datetime import date

import numpy as np
import pytest

from evi_weights.calculator import (
    apply_constraints,
    calculate_evi_weights,
    combine_scores,
    compute_adjustment_factor,
    compute_score,
    winsorize_score,
)
from evi_weights.config import (
    AdjustmentConfig,
    BaselineConfig,
    CombineMetricsConfig,
    ConstraintsConfig,
    EVIConfig,
    RegionConfig,
    ScoringConfig,
    WinsorizeConfig,
)
from evi_weights.data_provider import generate_sample_data
from evi_weights.models import RegionData, RegionScore, ValuationSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> EVIConfig:
    """Build an EVIConfig with sensible defaults, applying overrides."""
    regions = [
        RegionConfig(name="North America", index_proxy="S&P 500", etf_ticker="SPY"),
        RegionConfig(name="Europe", index_proxy="Stoxx Europe 600", etf_ticker="VGK"),
        RegionConfig(name="Emerging Markets", index_proxy="MSCI EM IMI", etf_ticker="EEM"),
        RegionConfig(name="Small Caps", index_proxy="MSCI World Small Cap", etf_ticker="VSS"),
        RegionConfig(name="Japan", index_proxy="MSCI Japan", etf_ticker="EWJ"),
        RegionConfig(name="Pacific ex-Japan", index_proxy="MSCI Pacific ex-Japan", etf_ticker="EPP"),
    ]
    defaults = dict(
        as_of_date=date(2025, 12, 31),
        regions=regions,
        baseline=BaselineConfig(),
        scoring=ScoringConfig(),
        combine_metrics=CombineMetricsConfig(),
        adjustment=AdjustmentConfig(),
        constraints=ConstraintsConfig(),
    )
    defaults.update(overrides)
    return EVIConfig(**defaults)


def _make_region_data(
    name: str,
    mcap_weight: float,
    current_pe: float,
    current_pb: float,
    baseline_pe: float = 16.0,
    baseline_pb: float = 2.0,
) -> RegionData:
    """Build RegionData with a long enough synthetic history for baseline computation."""
    history = []
    for q in range(48):
        year = 2014 + q // 4
        month = [3, 6, 9, 12][q % 4]
        day = 30 if month in (6, 9) else 31
        history.append(ValuationSnapshot(
            date=date(year, month, day),
            pe_ratio=baseline_pe + (q % 3 - 1) * 0.5,
            pb_ratio=baseline_pb + (q % 3 - 1) * 0.1,
        ))
    history[-1] = ValuationSnapshot(
        date=date(2025, 12, 31),
        pe_ratio=current_pe,
        pb_ratio=current_pb,
    )
    return RegionData(
        name=name,
        index_proxy="proxy",
        etf_ticker="TICK",
        mcap_weight=mcap_weight,
        current=history[-1],
        history=history,
    )


# ===========================================================================
# TestScoreProperties
# ===========================================================================

class TestScoreProperties:
    def test_log_ratio_antisymmetry(self):
        """log(a/b) = -log(b/a)"""
        a, b = 20.0, 15.0
        s1 = compute_score(a, b, method="log_ratio")
        s2 = compute_score(b, a, method="log_ratio")
        assert abs(s1 + s2) < 1e-12

    def test_log_ratio_additivity(self):
        """log(a/b) + log(b/c) = log(a/c)"""
        a, b, c = 25.0, 20.0, 15.0
        s_ab = compute_score(a, b, method="log_ratio")
        s_bc = compute_score(b, c, method="log_ratio")
        s_ac = compute_score(a, c, method="log_ratio")
        assert abs(s_ab + s_bc - s_ac) < 1e-12

    def test_score_strictly_monotone_in_current(self):
        """Higher current value → higher score (overvaluation signal)."""
        baseline = 18.0
        s_lo = compute_score(15.0, baseline, method="log_ratio")
        s_hi = compute_score(25.0, baseline, method="log_ratio")
        assert s_hi > s_lo

    def test_score_strictly_monotone_decreasing_in_baseline(self):
        """Higher baseline → lower score (makes current look cheaper)."""
        current = 20.0
        s_lo_base = compute_score(current, 15.0, method="log_ratio")
        s_hi_base = compute_score(current, 25.0, method="log_ratio")
        assert s_lo_base > s_hi_base

    def test_score_zero_when_equal(self):
        """score(x, x) = 0 for any positive x."""
        for x in [5.0, 15.0, 50.0, 100.0]:
            assert abs(compute_score(x, x, method="log_ratio")) < 1e-12

    def test_zscore_proportional(self):
        """zscore(2x, x) = 1.0"""
        x = 15.0
        s = compute_score(2 * x, x, method="zscore")
        assert abs(s - 1.0) < 1e-12


# ===========================================================================
# TestWinsorizeProperties
# ===========================================================================

class TestWinsorizeProperties:
    def test_idempotent(self):
        """winsorize(winsorize(s)) = winsorize(s)"""
        for s in [-5.0, -2.5, 0.0, 1.3, 2.5, 4.0]:
            once = winsorize_score(s)
            twice = winsorize_score(once)
            assert abs(once - twice) < 1e-12

    def test_preserves_ordering(self):
        """a < b → winsorize(a) ≤ winsorize(b)"""
        pairs = [(-3.0, -1.0), (-1.0, 0.0), (0.0, 2.0), (2.0, 3.0)]
        for a, b in pairs:
            assert winsorize_score(a) <= winsorize_score(b) + 1e-12

    def test_within_bounds(self):
        """All outputs fall within [-2.5, 2.5] for a range of inputs."""
        rng = np.random.default_rng(123)
        for s in rng.uniform(-10, 10, 100):
            w = winsorize_score(float(s))
            assert -2.5 <= w <= 2.5


# ===========================================================================
# TestAdjustmentFactorProperties
# ===========================================================================

class TestAdjustmentFactorProperties:
    def test_always_positive(self):
        """exp(-k*s) > 0 for all finite s."""
        for s in [-5.0, -1.0, 0.0, 1.0, 5.0]:
            f = compute_adjustment_factor(s, function="exp_score", strength_k=0.8)
            assert f > 0

    def test_strictly_decreasing_in_score(self):
        """Higher score → lower adjustment factor."""
        scores = [-2.0, -1.0, 0.0, 0.5, 1.0, 2.0]
        factors = [
            compute_adjustment_factor(s, function="exp_score", strength_k=0.8)
            for s in scores
        ]
        for i in range(len(factors) - 1):
            assert factors[i] > factors[i + 1]

    def test_neutral_at_zero(self):
        """f(0) = 1.0"""
        f = compute_adjustment_factor(0.0, function="exp_score", strength_k=0.8)
        assert abs(f - 1.0) < 1e-12

    def test_reciprocal_symmetry(self):
        """f(s) * f(-s) = 1"""
        for s in [0.3, 0.8, 1.5, 2.0]:
            f_pos = compute_adjustment_factor(s, function="exp_score", strength_k=0.8)
            f_neg = compute_adjustment_factor(-s, function="exp_score", strength_k=0.8)
            assert abs(f_pos * f_neg - 1.0) < 1e-12

    def test_stronger_k_more_extreme_factors(self):
        """Larger k → factors deviate more from 1.0 for non-zero scores."""
        s = 0.5
        f_weak = compute_adjustment_factor(s, function="exp_score", strength_k=0.3)
        f_strong = compute_adjustment_factor(s, function="exp_score", strength_k=1.5)
        assert abs(f_strong - 1.0) > abs(f_weak - 1.0)

    def test_k_zero_is_identity(self):
        """f(s, k=0) = 1.0 for all s."""
        for s in [-2.0, 0.0, 1.0, 3.0]:
            f = compute_adjustment_factor(s, function="exp_score", strength_k=0.0)
            assert abs(f - 1.0) < 1e-12


# ===========================================================================
# TestCombineScoresProperties
# ===========================================================================

class TestCombineScoresProperties:
    def test_weights_sum_property(self):
        """combine(s, s) = s when both metrics agree."""
        for s in [-1.0, 0.0, 0.5, 2.0]:
            result = combine_scores(s, s, pe_weight=0.6, pb_weight=0.4)
            assert abs(result - s) < 1e-12

    def test_bounded_by_inputs(self):
        """Result lies between min(pe, pb) and max(pe, pb)."""
        cases = [(0.5, -0.3), (-1.0, 0.2), (0.0, 1.5)]
        for pe, pb in cases:
            result = combine_scores(pe, pb, pe_weight=0.6, pb_weight=0.4)
            assert min(pe, pb) - 1e-12 <= result <= max(pe, pb) + 1e-12

    def test_linear_in_scores(self):
        """f(a*pe, a*pb) = a * f(pe, pb) — linearity (homogeneity)."""
        pe, pb = 0.5, -0.3
        a = 2.5
        base = combine_scores(pe, pb, pe_weight=0.6, pb_weight=0.4)
        scaled = combine_scores(a * pe, a * pb, pe_weight=0.6, pb_weight=0.4)
        assert abs(scaled - a * base) < 1e-12


# ===========================================================================
# TestConstraintProperties
# ===========================================================================

class TestConstraintProperties:
    def _make_scores(self, weights, mcap_weights):
        scores = []
        for i, (w, m) in enumerate(zip(weights, mcap_weights)):
            rs = RegionScore(name=f"R{i}", mcap_weight=m)
            rs.final_weight = w
            scores.append(rs)
        return scores

    def test_sum_to_one_invariant(self):
        """Constraint solver preserves sum-to-one across 50 random Dirichlet inputs."""
        rng = np.random.default_rng(42)
        for _ in range(50):
            raw = rng.dirichlet(np.ones(6))
            mcap = rng.dirichlet(np.ones(6))
            scores = self._make_scores(raw.tolist(), mcap.tolist())
            apply_constraints(scores, floor=0.02, ceiling=0.60,
                              max_overweight_pp=7.5, max_underweight_pp=-7.5)
            total = sum(s.final_weight for s in scores)
            assert abs(total - 1.0) < 1e-6, f"Sum = {total}"

    def test_all_weights_nonnegative(self):
        """All constrained weights are non-negative across 50 random inputs."""
        rng = np.random.default_rng(99)
        for _ in range(50):
            raw = rng.dirichlet(np.ones(6))
            mcap = rng.dirichlet(np.ones(6))
            scores = self._make_scores(raw.tolist(), mcap.tolist())
            apply_constraints(scores, floor=0.02, ceiling=0.60,
                              max_overweight_pp=7.5, max_underweight_pp=-7.5)
            for s in scores:
                assert s.final_weight >= -1e-10

    @pytest.mark.parametrize("floor_val", [0.01, 0.02, 0.05, 0.10])
    def test_floor_constraint_met(self, floor_val):
        """All weights ≥ floor after constraint application."""
        rng = np.random.default_rng(7)
        raw = rng.dirichlet(np.ones(6))
        mcap = rng.dirichlet(np.ones(6))
        scores = self._make_scores(raw.tolist(), mcap.tolist())
        apply_constraints(scores, floor=floor_val, ceiling=0.60,
                          max_overweight_pp=50, max_underweight_pp=-50)
        for s in scores:
            assert s.final_weight >= floor_val - 1e-6

    @pytest.mark.parametrize("ceiling_val", [0.30, 0.40, 0.50, 0.60])
    def test_ceiling_always_respected(self, ceiling_val):
        """All weights ≤ ceiling after constraint application."""
        rng = np.random.default_rng(11)
        raw = rng.dirichlet(np.ones(6))
        mcap = rng.dirichlet(np.ones(6))
        scores = self._make_scores(raw.tolist(), mcap.tolist())
        apply_constraints(scores, floor=0.02, ceiling=ceiling_val,
                          max_overweight_pp=50, max_underweight_pp=-50)
        for s in scores:
            assert s.final_weight <= ceiling_val + 1e-6


# ===========================================================================
# TestPipelineMonotonicity
# ===========================================================================

class TestPipelineMonotonicity:
    def test_cheaper_region_gets_more_weight(self):
        """A region with lower P/E should get higher EVI weight (all else equal)."""
        config = _make_config(
            constraints=ConstraintsConfig(
                weight_floor=0.0, weight_ceiling=1.0,
                max_overweight_pp=100, max_underweight_pp=-100,
                shrinkage_to_mcap_lambda=0.0, turnover_cap_pp=None,
            ),
        )
        cheap = _make_region_data("Cheap", 0.5, current_pe=12.0, current_pb=1.5)
        expensive = _make_region_data("Expensive", 0.5, current_pe=28.0, current_pb=4.0)
        result = calculate_evi_weights(config, [cheap, expensive])
        w = {rs.name: rs.final_weight for rs in result.region_scores}
        assert w["Cheap"] > w["Expensive"]

    def test_shrinkage_interpolation(self):
        """lambda=0 → pure EVI; lambda=1 → weights ≈ mcap."""
        config_pure = _make_config(
            constraints=ConstraintsConfig(
                weight_floor=0.0, weight_ceiling=1.0,
                max_overweight_pp=100, max_underweight_pp=-100,
                shrinkage_to_mcap_lambda=0.0, turnover_cap_pp=None,
            ),
        )
        config_mcap = _make_config(
            constraints=ConstraintsConfig(
                weight_floor=0.0, weight_ceiling=1.0,
                max_overweight_pp=100, max_underweight_pp=-100,
                shrinkage_to_mcap_lambda=1.0, turnover_cap_pp=None,
            ),
        )
        data = generate_sample_data(config_pure)
        result_pure = calculate_evi_weights(config_pure, data)
        result_mcap = calculate_evi_weights(config_mcap, data)

        # Pure EVI should differ from mcap
        any_diff = any(
            abs(rs.final_weight - rs.mcap_weight) > 0.001
            for rs in result_pure.region_scores
        )
        assert any_diff

        # Full shrinkage should be close to mcap
        for rs in result_mcap.region_scores:
            assert abs(rs.final_weight - rs.mcap_weight) < 0.01

    def test_higher_k_means_larger_spread(self):
        """k=1.5 produces more spread from mcap than k=0.3."""
        def _spread(k):
            config = _make_config(
                adjustment=AdjustmentConfig(function="exp_score", strength_k=k),
                constraints=ConstraintsConfig(
                    weight_floor=0.0, weight_ceiling=1.0,
                    max_overweight_pp=100, max_underweight_pp=-100,
                    shrinkage_to_mcap_lambda=0.0, turnover_cap_pp=None,
                ),
            )
            data = generate_sample_data(config)
            result = calculate_evi_weights(config, data)
            return sum(
                abs(rs.final_weight - rs.mcap_weight) for rs in result.region_scores
            )

        assert _spread(1.5) > _spread(0.3)

    def test_higher_lambda_means_closer_to_mcap(self):
        """lambda=0.8 produces weights closer to mcap than lambda=0.0."""
        def _distance(lam):
            config = _make_config(
                constraints=ConstraintsConfig(
                    weight_floor=0.0, weight_ceiling=1.0,
                    max_overweight_pp=100, max_underweight_pp=-100,
                    shrinkage_to_mcap_lambda=lam, turnover_cap_pp=None,
                ),
            )
            data = generate_sample_data(config)
            result = calculate_evi_weights(config, data)
            return sum(
                abs(rs.final_weight - rs.mcap_weight) for rs in result.region_scores
            )

        assert _distance(0.0) > _distance(0.8)


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:
    def test_single_region(self):
        """Single region → weight = 1.0."""
        config = _make_config(
            regions=[RegionConfig(name="North America", index_proxy="S&P 500", etf_ticker="SPY")],
            constraints=ConstraintsConfig(
                weight_floor=0.0, weight_ceiling=1.0,
                max_overweight_pp=100, max_underweight_pp=-100,
                shrinkage_to_mcap_lambda=0.0, turnover_cap_pp=None,
            ),
        )
        data = generate_sample_data(config)
        result = calculate_evi_weights(config, data)
        assert len(result.region_scores) == 1
        assert abs(result.region_scores[0].final_weight - 1.0) < 1e-6

    def test_all_regions_identically_valued(self):
        """When all scores = 0, weights should equal mcap weights."""
        config = _make_config(
            constraints=ConstraintsConfig(
                weight_floor=0.0, weight_ceiling=1.0,
                max_overweight_pp=100, max_underweight_pp=-100,
                shrinkage_to_mcap_lambda=0.0, turnover_cap_pp=None,
            ),
        )
        # Create regions where current = baseline (score = 0)
        regions = [
            _make_region_data("A", 0.4, current_pe=16.0, current_pb=2.0,
                              baseline_pe=16.0, baseline_pb=2.0),
            _make_region_data("B", 0.35, current_pe=16.0, current_pb=2.0,
                              baseline_pe=16.0, baseline_pb=2.0),
            _make_region_data("C", 0.25, current_pe=16.0, current_pb=2.0,
                              baseline_pe=16.0, baseline_pb=2.0),
        ]
        result = calculate_evi_weights(config, regions)
        for rs in result.region_scores:
            assert abs(rs.final_weight - rs.mcap_weight) < 0.02

    def test_empty_region_data(self):
        """Empty input → empty result."""
        config = _make_config()
        result = calculate_evi_weights(config, [])
        assert len(result.region_scores) == 0
