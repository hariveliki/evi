"""Integration tests for the full EVI calculation pipeline."""

import json
import math
from io import StringIO

import pytest

from evi_weights.calculator import calculate_evi_weights
from evi_weights.config import load_config
from evi_weights.data_provider import generate_sample_data


class TestFullPipeline:
    @pytest.fixture
    def config(self):
        return load_config()

    @pytest.fixture
    def region_data(self, config):
        return generate_sample_data(config)

    def test_produces_results_for_all_regions(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        assert len(result.region_scores) == 6

    def test_weights_sum_to_one(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        total = sum(rs.final_weight for rs in result.region_scores)
        assert abs(total - 1.0) < 1e-6

    def test_all_weights_positive(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            assert rs.final_weight > 0

    def test_floor_constraint_respected(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            assert rs.final_weight >= config.constraints.weight_floor - 1e-6

    def test_ceiling_constraint_respected(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            assert rs.final_weight <= config.constraints.weight_ceiling + 1e-6

    def test_overweight_constraint_respected(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            delta_pp = (rs.final_weight - rs.mcap_weight) * 100
            assert delta_pp <= config.constraints.max_overweight_pp + 0.1

    def test_underweight_constraint_respected(self, config, region_data):
        """Underweight constraint is respected unless overridden by the absolute ceiling."""
        result = calculate_evi_weights(config, region_data)
        ceiling = config.constraints.weight_ceiling
        for rs in result.region_scores:
            delta_pp = (rs.final_weight - rs.mcap_weight) * 100
            if rs.mcap_weight <= ceiling:
                assert delta_pp >= config.constraints.max_underweight_pp - 0.1
            else:
                assert rs.final_weight <= ceiling + 1e-6

    def test_evi_differs_from_mcap(self, config, region_data):
        """EVI weights should differ from pure market cap weights."""
        result = calculate_evi_weights(config, region_data)
        any_different = any(
            abs(rs.final_weight - rs.mcap_weight) > 0.001
            for rs in result.region_scores
        )
        assert any_different, "EVI weights should differ from market cap weights"

    def test_overvalued_regions_lose_weight(self, config, region_data):
        """Regions with positive composite scores should tend to have lower EVI weight."""
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            if rs.composite_score > 0.1:
                assert rs.adjustment_factor < 1.0

    def test_undervalued_regions_gain_weight(self, config, region_data):
        """Regions with negative composite scores should tend to have higher adjustment."""
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            if rs.composite_score < -0.1:
                assert rs.adjustment_factor > 1.0

    def test_diagnostics_present(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        for rs in result.region_scores:
            assert rs.current_pe is not None
            assert rs.baseline_pe is not None
            assert rs.adjustment_factor > 0

    def test_to_dict_output(self, config, region_data):
        result = calculate_evi_weights(config, region_data)
        rows = result.to_dict()
        assert len(rows) == 6
        assert all("Region" in r for r in rows)
        assert all("EVI Weight" in r for r in rows)

    def test_turnover_cap_with_previous_weights(self, config, region_data):
        result1 = calculate_evi_weights(config, region_data)
        prev = {rs.name: rs.mcap_weight for rs in result1.region_scores}

        result2 = calculate_evi_weights(config, region_data, previous_weights=prev)
        total_turnover = sum(
            abs(rs.final_weight - prev.get(rs.name, 0))
            for rs in result2.region_scores
        )
        assert total_turnover <= config.constraints.turnover_cap_pp / 100.0 + 0.01


class TestCLI:
    def test_cli_runs_without_error(self):
        from evi_weights.cli import main
        main(argv=[])

    def test_cli_verbose_mode(self):
        from evi_weights.cli import main
        main(argv=["--verbose"])

    def test_cli_json_output(self, capsys):
        from evi_weights.cli import main
        main(argv=["--output", "json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "regions" in data
        assert len(data["regions"]) == 6
        assert abs(data["total_weight"] - 1.0) < 0.001
