"""Integration tests for the FastAPI endpoints.

Uses httpx.TestClient against the actual app with a real test database.
Set DATABASE_URL env var to point at a test PostgreSQL instance.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Skip all tests if no DATABASE_URL is configured
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set — skipping API integration tests",
)


@pytest.fixture(scope="module")
def client():
    # Run migrations on the test DB before tests
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    from src.api.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_live_vehicles_empty(client):
    res = client.get("/api/vehicles/live")
    assert res.status_code == 200
    data = res.json()
    assert "vehicles" in data
    assert "count" in data
    assert isinstance(data["vehicles"], list)


def test_live_vehicles_mode_filter(client):
    res = client.get("/api/vehicles/live?mode=bus")
    assert res.status_code == 200


def test_history_requires_route(client):
    res = client.get("/api/vehicles/history")
    assert res.status_code == 422  # missing required 'route' param


def test_history_valid(client):
    res = client.get("/api/vehicles/history?route=33&hours=1")
    assert res.status_code == 200
    data = res.json()
    assert data["route"] == "33"
    assert isinstance(data["points"], list)


def test_delays(client):
    res = client.get("/api/analytics/delays")
    assert res.status_code == 200
    data = res.json()
    assert "routes" in data


def test_heatmap_geojson(client):
    res = client.get("/api/analytics/heatmap")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data


def test_route_efficiency(client):
    res = client.get("/api/analytics/route-efficiency")
    assert res.status_code == 200


def test_summary(client):
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "live_vehicle_count" in data
    assert "as_of" in data
