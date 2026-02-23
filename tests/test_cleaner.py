"""Tests for the data cleaning / normalization layer."""

import pytest

from src.pipeline.cleaner import (
    clean_bus_record,
    clean_bus_records,
    clean_train_record,
    clean_alert_record,
    _parse_offset,
)


# ── Bus cleaning ──────────────────────────────────────────────


def test_clean_bus_record_valid():
    raw = {
        "VehicleID": "4042",
        "Route": "33",
        "lat": "39.9526",
        "lng": "-75.1652",
        "heading": "270",
        "Speed": "12.5",
        "Offset": "2",
        "destination": "10th-Chesnut",
    }
    record = clean_bus_record(raw)
    assert record is not None
    assert record.vehicle_id == "4042"
    assert record.route == "33"
    assert record.mode == "bus"
    assert record.lat == pytest.approx(39.9526)
    assert record.lon == pytest.approx(-75.1652)
    assert record.offset_sec == 120  # 2 minutes → 120 seconds
    assert record.destination == "10th-Chesnut"


def test_clean_bus_record_trolley():
    raw = {"VehicleID": "1", "Route": "15", "lat": "39.95", "lng": "-75.16"}
    record = clean_bus_record(raw)
    assert record is not None
    assert record.mode == "trolley"


def test_clean_bus_record_missing_required_fields():
    raw = {"VehicleID": "999"}  # missing lat/lon/route
    record = clean_bus_record(raw)
    assert record is None


def test_clean_bus_record_zero_coordinates():
    raw = {"VehicleID": "1", "Route": "33", "lat": "0.0", "lng": "0.0"}
    record = clean_bus_record(raw)
    assert record is None


def test_clean_bus_records_filters_bad():
    raw_list = [
        {"VehicleID": "1", "Route": "33", "lat": "39.95", "lng": "-75.16"},
        {"VehicleID": "bad"},  # malformed
    ]
    records = clean_bus_records(raw_list)
    assert len(records) == 1


# ── Train cleaning ────────────────────────────────────────────


def test_clean_train_record_valid():
    raw = {
        "trainno": "9315",
        "line": "Media/Wawa",
        "lat": "39.900",
        "lon": "-75.300",
        "late": "5",
        "dest": "Center City",
        "heading": "90",
    }
    record = clean_train_record(raw)
    assert record is not None
    assert record.vehicle_id == "9315"
    assert record.route == "Media/Wawa"
    assert record.mode == "rail"
    assert record.offset_sec == 300  # 5 minutes


def test_clean_train_record_no_delay():
    raw = {"trainno": "1", "lat": "39.9", "lon": "-75.1", "late": "0"}
    record = clean_train_record(raw)
    assert record is not None
    assert record.offset_sec == 0


# ── Alert cleaning ────────────────────────────────────────────


def test_clean_alert_record():
    raw = {
        "route_id": "33",
        "current_message": "Delays expected",
        "advisory_message": "Use alternate route",
    }
    record = clean_alert_record(raw)
    assert record is not None
    assert record.route == "33"
    assert record.message == "Delays expected"


def test_clean_alert_record_no_route():
    raw = {"current_message": "System-wide delay"}
    record = clean_alert_record(raw)
    assert record is None


# ── Offset parsing ────────────────────────────────────────────


def test_parse_offset_numeric_string():
    assert _parse_offset("3") == 180


def test_parse_offset_negative():
    assert _parse_offset("-1") == -60


def test_parse_offset_zero():
    assert _parse_offset("0") == 0


def test_parse_offset_none():
    assert _parse_offset(None) is None


def test_parse_offset_text():
    # '2 min late' → 2 minutes → 120 seconds
    result = _parse_offset("2 min late")
    assert result == 120
