"""Database loading: bulk insert vehicle positions, alerts, and route stats."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.database.models import Alert, RouteStats, VehiclePosition
from src.pipeline.cleaner import AlertRecord, VehiclePositionRecord

logger = logging.getLogger(__name__)

# On-time threshold: within 5 minutes (300 seconds) counts as on time
ON_TIME_THRESHOLD_SEC = 300


def bulk_insert_positions(records: list[VehiclePositionRecord], session: Session) -> int:
    """Batch insert vehicle positions. Returns number of rows inserted."""
    if not records:
        return 0

    rows = []
    for r in records:
        rows.append(
            {
                "vehicle_id": r.vehicle_id,
                "route": r.route,
                "mode": r.mode,
                "lat": r.lat,
                "lon": r.lon,
                "geom": f"SRID=4326;POINT({r.lon} {r.lat})",
                "heading": r.heading,
                "speed": r.speed,
                "offset_sec": r.offset_sec,
                "destination": r.destination,
                "fetched_at": r.fetched_at,
            }
        )

    session.execute(
        text(
            """
            INSERT INTO vehicle_positions
                (vehicle_id, route, mode, lat, lon, geom, heading, speed, offset_sec, destination, fetched_at)
            VALUES
                (:vehicle_id, :route, :mode, :lat, :lon, ST_GeomFromEWKT(:geom),
                 :heading, :speed, :offset_sec, :destination, :fetched_at)
            """
        ),
        rows,
    )
    logger.info("Inserted %d vehicle positions", len(rows))
    return len(rows)


def bulk_insert_alerts(records: list[AlertRecord], session: Session) -> int:
    """Insert alert records. Returns number of rows inserted."""
    if not records:
        return 0

    rows = [
        {
            "route": r.route,
            "message": r.message,
            "advisory_message": r.advisory_message,
            "fetched_at": r.fetched_at,
        }
        for r in records
    ]

    session.execute(
        text(
            """
            INSERT INTO alerts (route, message, advisory_message, fetched_at)
            VALUES (:route, :message, :advisory_message, :fetched_at)
            """
        ),
        rows,
    )
    logger.info("Inserted %d alerts", len(rows))
    return len(rows)


def upsert_route_stats(session: Session, window_minutes: int = 5) -> None:
    """Aggregate the last N minutes of vehicle positions into route_stats."""
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    snapshot_at = datetime.now(timezone.utc)

    result = session.execute(
        text(
            """
            SELECT
                route,
                mode,
                COUNT(*) AS vehicle_count,
                AVG(offset_sec) AS avg_delay_sec,
                100.0 * SUM(CASE WHEN offset_sec IS NULL OR ABS(offset_sec) <= :threshold THEN 1 ELSE 0 END)
                    / COUNT(*) AS on_time_pct
            FROM vehicle_positions
            WHERE fetched_at >= :since
            GROUP BY route, mode
            """
        ),
        {"since": since, "threshold": ON_TIME_THRESHOLD_SEC},
    )

    rows = result.fetchall()
    if not rows:
        return

    stats_rows = [
        {
            "route": row.route,
            "mode": row.mode,
            "snapshot_at": snapshot_at,
            "avg_delay_sec": float(row.avg_delay_sec) if row.avg_delay_sec is not None else None,
            "vehicle_count": int(row.vehicle_count),
            "on_time_pct": float(row.on_time_pct) if row.on_time_pct is not None else None,
        }
        for row in rows
    ]

    session.execute(
        text(
            """
            INSERT INTO route_stats (route, mode, snapshot_at, avg_delay_sec, vehicle_count, on_time_pct)
            VALUES (:route, :mode, :snapshot_at, :avg_delay_sec, :vehicle_count, :on_time_pct)
            """
        ),
        stats_rows,
    )
    logger.info("Upserted route_stats for %d routes", len(stats_rows))
