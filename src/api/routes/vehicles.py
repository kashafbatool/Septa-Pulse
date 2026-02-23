"""Vehicle position endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_db

router = APIRouter()


@router.get("/live")
def get_live_vehicles(
    route: Optional[str] = Query(None, description="Filter by route (e.g. '33', 'Media/Wawa')"),
    mode: Optional[str] = Query(None, description="Filter by mode: bus | trolley | rail"),
    db: Session = Depends(get_db),
):
    """Return vehicle positions from the last 90 seconds."""
    since = datetime.now(timezone.utc) - timedelta(seconds=90)

    sql = """
        SELECT DISTINCT ON (vehicle_id)
            id, vehicle_id, route, mode, lat, lon, heading, speed, offset_sec, destination, fetched_at
        FROM vehicle_positions
        WHERE fetched_at >= :since
        {route_filter}
        {mode_filter}
        ORDER BY vehicle_id, fetched_at DESC
    """
    params: dict = {"since": since}
    route_filter = ""
    mode_filter = ""

    if route:
        route_filter = "AND route = :route"
        params["route"] = route
    if mode:
        mode_filter = "AND mode = :mode"
        params["mode"] = mode

    sql = sql.format(route_filter=route_filter, mode_filter=mode_filter)
    rows = db.execute(text(sql), params).fetchall()

    return {
        "count": len(rows),
        "vehicles": [
            {
                "id": r.id,
                "vehicle_id": r.vehicle_id,
                "route": r.route,
                "mode": r.mode,
                "lat": r.lat,
                "lon": r.lon,
                "heading": r.heading,
                "speed": r.speed,
                "offset_sec": r.offset_sec,
                "destination": r.destination,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
        ],
    }


@router.get("/history")
def get_vehicle_history(
    route: str = Query(..., description="Route to query history for"),
    hours: int = Query(6, ge=1, le=72, description="How many hours back to look"),
    db: Session = Depends(get_db),
):
    """Return historical vehicle trail points for a given route."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = db.execute(
        text(
            """
            SELECT vehicle_id, lat, lon, offset_sec, destination, fetched_at
            FROM vehicle_positions
            WHERE route = :route AND fetched_at >= :since
            ORDER BY fetched_at ASC
            LIMIT 50000
            """
        ),
        {"route": route, "since": since},
    ).fetchall()

    return {
        "route": route,
        "hours": hours,
        "count": len(rows),
        "points": [
            {
                "vehicle_id": r.vehicle_id,
                "lat": r.lat,
                "lon": r.lon,
                "offset_sec": r.offset_sec,
                "destination": r.destination,
                "fetched_at": r.fetched_at.isoformat() if r.fetched_at else None,
            }
            for r in rows
        ],
    }


@router.get("/routes")
def get_routes(
    mode: Optional[str] = Query(None, description="Filter by mode: bus | trolley | rail"),
    db: Session = Depends(get_db),
):
    """Return all routes seen in the last 24 hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    params: dict = {"since": since}
    mode_filter = ""
    if mode:
        mode_filter = "AND mode = :mode"
        params["mode"] = mode

    rows = db.execute(
        text(
            f"""
            SELECT DISTINCT route, mode
            FROM vehicle_positions
            WHERE fetched_at >= :since {mode_filter}
            ORDER BY route
            """
        ),
        params,
    ).fetchall()

    return {"routes": [{"route": r.route, "mode": r.mode} for r in rows]}
