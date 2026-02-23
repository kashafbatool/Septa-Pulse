"""Tests for the SEPTA API fetcher."""

import pytest
import responses as resp_lib

from src.pipeline.fetcher import SEPTAClient, SEPTAAPIError


FAKE_BASE = "https://fake-septa.test/api"


@pytest.fixture
def client():
    return SEPTAClient(base_url=FAKE_BASE)


@resp_lib.activate
def test_get_all_buses_returns_list(client):
    resp_lib.add(
        resp_lib.GET,
        f"{FAKE_BASE}/TransitViewAll/index.php",
        json={"bus": [{"VehicleID": "1", "Route": "33", "lat": "39.95", "lng": "-75.16"}]},
        status=200,
    )
    buses = client.get_all_buses()
    assert isinstance(buses, list)
    assert len(buses) == 1
    assert buses[0]["VehicleID"] == "1"


@resp_lib.activate
def test_get_all_buses_empty_on_bad_shape(client):
    resp_lib.add(
        resp_lib.GET,
        f"{FAKE_BASE}/TransitViewAll/index.php",
        json={"unexpected": "shape"},
        status=200,
    )
    buses = client.get_all_buses()
    assert buses == []


@resp_lib.activate
def test_get_train_positions_list(client):
    resp_lib.add(
        resp_lib.GET,
        f"{FAKE_BASE}/TrainView/index.php",
        json=[{"trainno": "9315", "lat": "40.00", "lon": "-75.20", "line": "Media/Wawa", "late": "2"}],
        status=200,
    )
    trains = client.get_train_positions()
    assert len(trains) == 1
    assert trains[0]["trainno"] == "9315"


@resp_lib.activate
def test_retries_on_500_then_raises(client):
    for _ in range(3):
        resp_lib.add(
            resp_lib.GET,
            f"{FAKE_BASE}/TransitViewAll/index.php",
            status=500,
        )
    with pytest.raises(SEPTAAPIError):
        client.get_all_buses()


@resp_lib.activate
def test_get_alerts(client):
    resp_lib.add(
        resp_lib.GET,
        f"{FAKE_BASE}/Alerts/index.php",
        json=[
            {"route_id": "33", "current_message": "Delays due to traffic", "advisory_message": ""},
        ],
        status=200,
    )
    alerts = client.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["route_id"] == "33"
