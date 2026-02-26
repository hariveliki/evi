"""Tests for configuration loading."""

import tempfile
from datetime import date
from pathlib import Path

import pytest
import yaml

from evi_weights.config import EVIConfig, load_config


class TestLoadConfig:
    def test_load_default_config(self):
        config = load_config()
        assert isinstance(config, EVIConfig)
        assert config.rebalance_frequency == "quarterly"
        assert config.data_lag_days == 5
        assert len(config.regions) == 6

    def test_region_names(self):
        config = load_config()
        names = {r.name for r in config.regions}
        expected = {
            "North America", "Europe", "Emerging Markets",
            "Small Caps", "Japan", "Pacific ex-Japan",
        }
        assert names == expected

    def test_scoring_config(self):
        config = load_config()
        assert config.scoring.score_method == "log_ratio"
        assert config.scoring.winsorize.enabled is True
        assert config.scoring.winsorize.limits == (-2.5, 2.5)

    def test_combine_metrics(self):
        config = load_config()
        assert config.combine_metrics.metric_weights["pe"] == 0.6
        assert config.combine_metrics.metric_weights["pb"] == 0.4

    def test_adjustment_config(self):
        config = load_config()
        assert config.adjustment.function == "exp_score"
        assert config.adjustment.strength_k == 0.8

    def test_constraints_config(self):
        config = load_config()
        assert config.constraints.weight_floor == 0.02
        assert config.constraints.weight_ceiling == 0.60
        assert config.constraints.shrinkage_to_mcap_lambda == 0.20

    def test_effective_date(self):
        config = load_config()
        delta = config.as_of_date - config.effective_date
        assert delta.days == 5

    def test_custom_config(self):
        custom = {
            "calculation_parameters": {
                "rebalance_frequency": "monthly",
                "data_lag_days": 3,
                "scoring": {
                    "score_method": "zscore",
                    "winsorize": {"enabled": False},
                },
                "adjustment": {
                    "function": "inverse_ratio",
                    "alpha": 0.6,
                    "beta": 0.4,
                },
            },
            "regions": [
                {
                    "name": "Test Region",
                    "index_proxy": "Test Index",
                    "etf_ticker": "TEST",
                },
            ],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(custom, f)
            f.flush()
            config = load_config(f.name)

        assert config.rebalance_frequency == "monthly"
        assert config.data_lag_days == 3
        assert config.scoring.score_method == "zscore"
        assert config.scoring.winsorize.enabled is False
        assert config.adjustment.function == "inverse_ratio"
        assert len(config.regions) == 1
        assert config.regions[0].name == "Test Region"
