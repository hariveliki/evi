"""Tests for the SQLite database layer."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from evi_weights.config import EVIConfig, load_config
from evi_weights.calculator import calculate_evi_weights
from evi_weights.data_provider import generate_sample_data
from evi_weights.db.migrations import create_all
from evi_weights.db.models import Base
from evi_weights.db.repository import Repository


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:")
    create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def repo(session):
    return Repository(session)


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def region_data(config):
    return generate_sample_data(config)


@pytest.fixture
def result(config, region_data):
    return calculate_evi_weights(config, region_data)


class TestSnapshots:
    def test_save_and_load_snapshots(self, repo, session, region_data):
        count = repo.save_snapshots(region_data, source="sample")
        session.commit()
        assert count > 0

        rows = repo.load_snapshots("North America", source="sample")
        assert len(rows) > 0
        assert rows[0].region_name == "North America"

    def test_save_snapshots_idempotent(self, repo, session, region_data):
        count1 = repo.save_snapshots(region_data, source="sample")
        session.commit()
        count2 = repo.save_snapshots(region_data, source="sample")
        session.commit()
        assert count2 == 0  # no new rows on second insert

    def test_load_snapshots_with_date_filter(self, repo, session, region_data):
        repo.save_snapshots(region_data, source="sample")
        session.commit()

        rows = repo.load_snapshots(
            "North America", source="sample",
            start_date=date(2020, 1, 1), end_date=date(2022, 12, 31),
        )
        for r in rows:
            assert date(2020, 1, 1) <= r.snapshot_date <= date(2022, 12, 31)


class TestCalculationRuns:
    def test_save_and_load_run(self, repo, session, config, result):
        run = repo.save_calculation_run(config, result, triggered_by="test")
        session.commit()
        assert run.id is not None

        loaded = repo.load_calculation_run(run.id)
        assert loaded is not None
        assert loaded.as_of_date == result.as_of_date
        assert len(loaded.region_results) == len(result.region_scores)

    def test_region_results_match(self, repo, session, config, result):
        run = repo.save_calculation_run(config, result)
        session.commit()

        loaded = repo.load_calculation_run(run.id)
        for rr in loaded.region_results:
            original = next(
                rs for rs in result.region_scores if rs.name == rr.region_name
            )
            assert abs(rr.final_weight - original.final_weight) < 1e-10
            assert abs(rr.composite_score - original.composite_score) < 1e-10

    def test_list_runs(self, repo, session, config, result):
        repo.save_calculation_run(config, result)
        repo.save_calculation_run(config, result, scenario_name="test-scenario")
        session.commit()

        runs = repo.list_runs()
        assert len(runs) == 2

    def test_config_deduplication(self, repo, session, config, result):
        run1 = repo.save_calculation_run(config, result)
        run2 = repo.save_calculation_run(config, result)
        session.commit()
        assert run1.config_id == run2.config_id


class TestScenarios:
    def test_save_and_load_scenario(self, repo, session, config, result):
        run1 = repo.save_calculation_run(config, result, scenario_name="v1")
        run2 = repo.save_calculation_run(config, result, scenario_name="v2")
        session.commit()

        scenario = repo.save_scenario(
            name="K sensitivity",
            run_labels=[(run1, "k=0.3"), (run2, "k=0.8")],
            description="Testing different k values",
        )
        session.commit()
        assert scenario.id is not None

        loaded = repo.load_scenario(scenario.id)
        assert loaded is not None
        assert loaded.name == "K sensitivity"
        assert len(loaded.runs) == 2


class TestListRegions:
    def test_list_regions_after_save(self, repo, session, region_data):
        repo.save_snapshots(region_data, source="sample")
        session.commit()

        regions = repo.list_regions()
        assert len(regions) == 6
        names = {r["name"] for r in regions}
        assert "North America" in names
        assert all(r["snapshot_count"] > 0 for r in regions)
