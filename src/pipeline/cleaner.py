"""Data cleaning and normalization for SEPTA API responses.

Converts raw JSON dicts into typed VehiclePositionRecord dataclasses,
dropping malformed records with a warning rather than crashing.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VehiclePositionRecord:
    vehicle_id: str
    route: str
    mode: str  # 'bus' | 'trolley' | 'rail'
    lat: float
    lon: float
    heading: Optional[int]
    speed: Optional[float]
    offset_sec: Optional[int]  # positive = late, negative = early
    destination: Optional[str]
    fetched_at: datetime


@dataclass
class AlertRecord:
    route: str
    message: Optional[str]
    advisory_message: Optional[str]
    fetched_at: datetime


def _parse_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: object) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_offset(raw_offset: object) -> Optional[int]:
    """Convert SEPTA offset string (e.g. '2 min late', '-1 min early') to seconds."""
    if raw_offset is None:
        return None
    s = str(raw_offset).strip().lower()
    # TransitView returns numeric strings like '2' or '-1' (minutes)
    try:
        return int(float(s)) * 60
    except ValueError:
        pass
    # Some endpoints return '2 min late'
    for word in s.split():
        try:
            minutes = float(word)
            return int(minutes * 60)
        except ValueError:
            continue
    return None


def clean_bus_record(
    raw: dict, fetched_at: Optional[datetime] = None
) -> Optional[VehiclePositionRecord]:
    """Normalize a single bus/trolley record from TransitViewAll."""
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc)

    lat = _parse_float(raw.get("lat"))
    lon = _parse_float(raw.get("lng") or raw.get("lon"))
    vehicle_id = str(raw.get("VehicleID", "")).strip()
    route = str(raw.get("Route", "")).strip()

    if not all([lat, lon, vehicle_id, route]):
        logger.debug("Dropping malformed bus record: %s", raw)
        return None

    if lat == 0.0 and lon == 0.0:
        logger.debug("Dropping zero-coordinate bus record: vehicle=%s", vehicle_id)
        return None

    # Distinguish trolleys (route numbers < 15 or contains 'T')
    mode = "trolley" if _is_trolley(route) else "bus"

    return VehiclePositionRecord(
        vehicle_id=vehicle_id,
        route=route,
        mode=mode,
        lat=lat,
        lon=lon,
        heading=_parse_int(raw.get("heading")),
        speed=_parse_float(raw.get("Speed")),
        offset_sec=_parse_offset(raw.get("Offset")),
        destination=str(raw.get("destination", "")).strip() or None,
        fetched_at=fetched_at,
    )


def clean_train_record(
    raw: dict, fetched_at: Optional[datetime] = None
) -> Optional[VehiclePositionRecord]:
    """Normalize a single regional rail record from TrainView."""
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc)

    lat = _parse_float(raw.get("lat"))
    lon = _parse_float(raw.get("lon"))
    train_no = str(raw.get("trainno", "")).strip()
    line = str(raw.get("line", "")).strip()

    if not all([lat, lon, train_no]):
        logger.debug("Dropping malformed train record: %s", raw)
        return None

    if lat == 0.0 and lon == 0.0:
        logger.debug("Dropping zero-coordinate train record: train=%s", train_no)
        return None

    # Delay from TrainView: 'late' field in minutes
    late_min = _parse_float(raw.get("late"))
    offset_sec = int(late_min * 60) if late_min is not None else None

    return VehiclePositionRecord(
        vehicle_id=train_no,
        route=line or train_no,
        mode="rail",
        lat=lat,
        lon=lon,
        heading=_parse_int(raw.get("heading")),
        speed=None,
        offset_sec=offset_sec,
        destination=str(raw.get("dest", "")).strip() or None,
        fetched_at=fetched_at,
    )


def clean_alert_record(
    raw: dict, fetched_at: Optional[datetime] = None
) -> Optional[AlertRecord]:
    """Normalize a single alert record."""
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc)

    route = str(raw.get("route_id", raw.get("route", ""))).strip()
    if not route:
        return None

    return AlertRecord(
        route=route,
        message=str(raw.get("current_message", "")).strip() or None,
        advisory_message=str(raw.get("advisory_message", "")).strip() or None,
        fetched_at=fetched_at,
    )


def clean_bus_records(raw_list: list[dict]) -> list[VehiclePositionRecord]:
    results = []
    for raw in raw_list:
        record = clean_bus_record(raw)
        if record:
            results.append(record)
    return results


def clean_train_records(raw_list: list[dict]) -> list[VehiclePositionRecord]:
    results = []
    for raw in raw_list:
        record = clean_train_record(raw)
        if record:
            results.append(record)
    return results


def clean_alert_records(raw_list: list[dict]) -> list[AlertRecord]:
    results = []
    for raw in raw_list:
        record = clean_alert_record(raw)
        if record:
            results.append(record)
    return results


def _is_trolley(route: str) -> bool:
    trolley_routes = {"10", "11", "13", "15", "34", "36", "101", "102"}
    return route.strip() in trolley_routes
