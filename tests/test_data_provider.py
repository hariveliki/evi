"""Tests for the data provider module."""

import json
import tempfile
from pathlib import Path

import pytest

from evi_weights.config import load_config
from evi_weights.data_provider import (
    export_data_to_json,
    generate_sample_data,
    get_region_data,
    load_data_from_json,
)


class TestGenerateSampleData:
    def test_generates_all_regions(self):
        config = load_config()
        data = generate_sample_data(config)
        assert len(data) == 6
        names = {r.name for r in data}
        assert "North America" in names
        assert "Japan" in names

    def test_mcap_weights_sum_to_one(self):
        config = load_config()
        data = generate_sample_data(config)
        total = sum(r.mcap_weight for r in data)
        assert abs(total - 1.0) < 1e-4

    def test_has_history(self):
        config = load_config()
        data = generate_sample_data(config)
        for region in data:
            assert len(region.history) > 20

    def test_current_values_present(self):
        config = load_config()
        data = generate_sample_data(config)
        for region in data:
            assert region.current.pe_ratio is not None
            assert region.current.pe_ratio > 0
            assert region.current.pb_ratio is not None
            assert region.current.pb_ratio > 0

    def test_deterministic_with_seed(self):
        config = load_config()
        data1 = generate_sample_data(config)
        data2 = generate_sample_data(config)
        for r1, r2 in zip(data1, data2):
            assert r1.current.pe_ratio == r2.current.pe_ratio
            assert r1.current.pb_ratio == r2.current.pb_ratio


class TestExportAndLoad:
    def test_roundtrip(self):
        config = load_config()
        data = generate_sample_data(config)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_data.json"
            export_data_to_json(data, path)

            loaded = load_data_from_json(path, config)

        assert len(loaded) == len(data)
        for orig, ld in zip(data, loaded):
            assert orig.name == ld.name
            assert orig.current.pe_ratio == ld.current.pe_ratio
            assert len(ld.history) == len(orig.history)


class TestGetRegionData:
    def test_sample_source(self):
        config = load_config()
        data = get_region_data(config, source="sample")
        assert len(data) == 6

    def test_json_source_requires_path(self):
        config = load_config()
        with pytest.raises(ValueError):
            get_region_data(config, source="json", json_path=None)
