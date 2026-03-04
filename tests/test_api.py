"""Tests for the FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from evi_weights.api.app import create_app
from evi_weights.api.dependencies import get_db, init_db, override_session_factory
from evi_weights.db.migrations import create_all


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    create_all(eng)
    return eng


@pytest.fixture(scope="module")
def session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="module")
def client(session_factory):
    override_session_factory(session_factory)
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestCalculateEndpoint:
    def test_calculate_sample(self, client):
        resp = client.post("/api/calculate", json={"source": "sample"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] >= 1
        assert len(data["regions"]) == 6
        assert abs(data["total_weight"] - 1.0) < 0.001

    def test_calculate_with_overrides(self, client):
        resp = client.post("/api/calculate", json={
            "source": "sample",
            "config_overrides": {"strength_k": 1.5, "shrinkage_lambda": 0.0},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert abs(data["total_weight"] - 1.0) < 0.001

    def test_calculate_with_scenario_name(self, client):
        resp = client.post("/api/calculate", json={
            "source": "sample",
            "scenario_name": "test-scenario",
        })
        assert resp.status_code == 200
        assert resp.json()["run_id"] >= 1


class TestRegionsEndpoint:
    def test_list_regions(self, client):
        # Ensure data exists
        client.post("/api/calculate", json={"source": "sample"})
        resp = client.get("/api/regions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_region_history(self, client):
        resp = client.get("/api/regions/North America/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["region_name"] == "North America"
        assert len(data["snapshots"]) > 0


class TestRunsEndpoint:
    def test_list_runs(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_get_run(self, client):
        # Get first run ID
        runs = client.get("/api/runs").json()
        run_id = runs[0]["id"]
        resp = client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run_id
        assert len(data["regions"]) == 6

    def test_get_nonexistent_run(self, client):
        resp = client.get("/api/runs/99999")
        assert resp.status_code == 404


class TestScenariosEndpoint:
    def test_compare_scenarios(self, client):
        resp = client.post("/api/scenarios/compare", json={
            "name": "K sensitivity test",
            "source": "sample",
            "variants": [
                {"label": "k=0.3", "config_overrides": {"strength_k": 0.3}},
                {"label": "k=1.5", "config_overrides": {"strength_k": 1.5}},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario_id"] >= 1
        assert len(data["variants"]) == 2
        # Different k should produce different weights
        w1 = {r["region_name"]: r["final_weight"] for r in data["variants"][0]["regions"]}
        w2 = {r["region_name"]: r["final_weight"] for r in data["variants"][1]["regions"]}
        any_diff = any(abs(w1[k] - w2[k]) > 0.001 for k in w1)
        assert any_diff


class TestBacktestEndpoint:
    def test_backtest(self, client):
        resp = client.post("/api/backtest", json={
            "start_date": "2020-01-01",
            "end_date": "2022-12-31",
            "source": "sample",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["points"]) > 0
        for pt in data["points"]:
            assert len(pt["regions"]) > 0


class TestConfigEndpoint:
    def test_get_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "adjustment" in data
        assert "constraints" in data

    def test_update_config(self, client):
        resp = client.put("/api/config", json={"strength_k": 1.2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjustment"]["strength_k"] == 1.2


class TestExportEndpoint:
    def test_export_csv(self, client):
        # Get a run ID first
        calc = client.post("/api/calculate", json={"source": "sample"}).json()
        run_id = calc["run_id"]
        resp = client.get(f"/api/export/csv?run_id={run_id}")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "region_name" in resp.text

    def test_export_json(self, client):
        calc = client.post("/api/calculate", json={"source": "sample"}).json()
        run_id = calc["run_id"]
        resp = client.get(f"/api/export/json?run_id={run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert len(data["regions"]) == 6

    def test_export_nonexistent_run(self, client):
        resp = client.get("/api/export/csv?run_id=99999")
        assert resp.status_code == 404
