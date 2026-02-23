"""Analytics endpoints: delays, heatmaps, route efficiency."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_db

router = APIRouter()


@router.get("/delays")
def get_delay_rankings(
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
    mode: Optional[str] = Query(
        None, description="Filter by mode: bus | trolley | rail"
    ),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return average delay per route, sorted worst-first."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    params: dict = {"since": since}
    mode_filter = ""
    if mode:
        mode_filter = "AND mode = :mode"
        params["mode"] = mode

    rows = db.execute(
        text(
            f"""
            SELECT
                route,
                mode,
                COUNT(*) AS observations,
                ROUND(AVG(offset_sec)::numeric, 1) AS avg_delay_sec,
                ROUND(MAX(offset_sec)::numeric, 1) AS max_delay_sec,
                ROUND(
                    100.0 * SUM(CASE WHEN offset_sec IS NULL OR ABS(offset_sec) <= 300 THEN 1 ELSE 0 END)
                    / COUNT(*), 1
                ) AS on_time_pct
            FROM vehicle_positions
            WHERE fetched_at >= :since AND offset_sec IS NOT NULL {mode_filter}
            GROUP BY route, mode
            HAVING COUNT(*) >= 5
            ORDER BY avg_delay_sec DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {**params, "limit": limit},
    ).fetchall()

    return {
        "hours": hours,
        "routes": [
            {
                "route": r.route,
                "mode": r.mode,
                "observations": r.observations,
                "avg_delay_sec": float(r.avg_delay_sec) if r.avg_delay_sec else None,
                "max_delay_sec": float(r.max_delay_sec) if r.max_delay_sec else None,
                "on_time_pct": float(r.on_time_pct) if r.on_time_pct else None,
            }
            for r in rows
        ],
    }


@router.get("/heatmap")
def get_heatmap(
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return GeoJSON FeatureCollection of vehicle positions for heatmap rendering."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    params: dict = {"since": since}
    mode_filter = ""
    if mode:
        mode_filter = "AND mode = :mode"
        params["mode"] = mode

    rows = db.execute(
        text(
            f"""
            SELECT lat, lon, offset_sec
            FROM vehicle_positions
            WHERE fetched_at >= :since {mode_filter}
            LIMIT 100000
            """
        ),
        params,
    ).fetchall()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
            "properties": {"offset_sec": r.offset_sec},
        }
        for r in rows
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "hours": hours,
    }


@router.get("/route-efficiency")
def get_route_efficiency(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Return on-time percentage per route from route_stats snapshots."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = db.execute(
        text(
            """
            SELECT
                route,
                mode,
                ROUND(AVG(on_time_pct)::numeric, 1) AS avg_on_time_pct,
                ROUND(AVG(avg_delay_sec)::numeric, 1) AS avg_delay_sec,
                ROUND(AVG(vehicle_count)::numeric, 0) AS avg_vehicle_count
            FROM route_stats
            WHERE snapshot_at >= :since
            GROUP BY route, mode
            ORDER BY avg_on_time_pct ASC
            LIMIT 50
            """
        ),
        {"since": since},
    ).fetchall()

    return {
        "hours": hours,
        "routes": [
            {
                "route": r.route,
                "mode": r.mode,
                "avg_on_time_pct": (
                    float(r.avg_on_time_pct) if r.avg_on_time_pct else None
                ),
                "avg_delay_sec": float(r.avg_delay_sec) if r.avg_delay_sec else None,
                "avg_vehicle_count": (
                    int(r.avg_vehicle_count) if r.avg_vehicle_count else None
                ),
            }
            for r in rows
        ],
    }


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """Return a high-level system snapshot for the dashboard header."""
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    live = db.execute(
        text(
            "SELECT COUNT(DISTINCT vehicle_id) AS cnt FROM vehicle_positions WHERE fetched_at >= :since"
        ),
        {"since": datetime.now(timezone.utc) - timedelta(seconds=90)},
    ).fetchone()

    delayed = db.execute(
        text(
            """
            SELECT COUNT(*) AS cnt FROM (
                SELECT DISTINCT ON (vehicle_id) vehicle_id, offset_sec
                FROM vehicle_positions WHERE fetched_at >= :since
                ORDER BY vehicle_id, fetched_at DESC
            ) sub WHERE offset_sec > 300
            """
        ),
        {"since": datetime.now(timezone.utc) - timedelta(seconds=90)},
    ).fetchone()

    total_24h = db.execute(
        text(
            "SELECT COUNT(*) AS cnt FROM vehicle_positions WHERE fetched_at >= :since"
        ),
        {"since": since_24h},
    ).fetchone()

    return {
        "live_vehicle_count": live.cnt if live else 0,
        "delayed_vehicle_count": delayed.cnt if delayed else 0,
        "positions_last_24h": total_24h.cnt if total_24h else 0,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
