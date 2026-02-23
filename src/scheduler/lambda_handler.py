"""SEPTA Pulse pipeline scheduler.

Dual-mode entry point:
  - AWS Lambda:  `handler(event, context)` is called by EventBridge every 30 seconds.
  - Local mode:  `python -m src.scheduler.lambda_handler` uses APScheduler.

Pipeline flow:
  1. Fetch  — pull raw data from SEPTA API
  2. Clean  — normalize and validate records
  3. Load   — bulk insert into PostgreSQL
  4. Stats  — aggregate route_stats for the last 5 minutes
"""

import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("septa_pulse.scheduler")

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))


def run_pipeline() -> dict:
    """Execute one full fetch → clean → load cycle. Returns a summary dict."""
    from src.database.connection import get_session
    from src.pipeline.cleaner import clean_alert_records, clean_bus_records, clean_train_records
    from src.pipeline.fetcher import SEPTAAPIError, SEPTAClient
    from src.pipeline.loader import bulk_insert_alerts, bulk_insert_positions, upsert_route_stats

    start = datetime.now(timezone.utc)
    client = SEPTAClient()
    summary: dict = {"started_at": start.isoformat(), "buses": 0, "trains": 0, "alerts": 0, "errors": []}

    # --- Fetch ---
    raw_buses, raw_trains, raw_alerts = [], [], []
    try:
        raw_buses = client.get_all_buses()
        logger.info("Fetched %d raw bus records", len(raw_buses))
    except SEPTAAPIError as exc:
        logger.error("Failed to fetch buses: %s", exc)
        summary["errors"].append(f"buses: {exc}")

    try:
        raw_trains = client.get_train_positions()
        logger.info("Fetched %d raw train records", len(raw_trains))
    except SEPTAAPIError as exc:
        logger.error("Failed to fetch trains: %s", exc)
        summary["errors"].append(f"trains: {exc}")

    try:
        raw_alerts = client.get_alerts()
        logger.info("Fetched %d raw alert records", len(raw_alerts))
    except SEPTAAPIError as exc:
        logger.error("Failed to fetch alerts: %s", exc)
        summary["errors"].append(f"alerts: {exc}")

    # --- Clean ---
    fetched_at = datetime.now(timezone.utc)
    bus_records = clean_bus_records(raw_buses)
    train_records = clean_train_records(raw_trains)
    alert_records = clean_alert_records(raw_alerts)

    logger.info(
        "Cleaned: %d buses, %d trains, %d alerts",
        len(bus_records),
        len(train_records),
        len(alert_records),
    )

    # --- Load ---
    with get_session() as session:
        summary["buses"] = bulk_insert_positions(bus_records + train_records, session)
        summary["alerts"] = bulk_insert_alerts(alert_records, session)
        upsert_route_stats(session)

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    summary["elapsed_sec"] = round(elapsed, 2)
    logger.info("Pipeline complete in %.2fs: %s", elapsed, summary)
    return summary


# ---------------------------------------------------------------------------
# AWS Lambda entry point
# ---------------------------------------------------------------------------

def handler(event: dict, context: object) -> dict:
    """AWS Lambda handler — invoked by EventBridge every 30 seconds."""
    logger.info("Lambda invoked: %s", event)
    return run_pipeline()


# ---------------------------------------------------------------------------
# Local scheduler entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from apscheduler.schedulers.blocking import BlockingScheduler

    logger.info("Starting local APScheduler (interval=%ds)", POLL_INTERVAL)
    # Run once immediately on startup
    try:
        run_pipeline()
    except Exception as exc:
        logger.error("Initial pipeline run failed: %s", exc)

    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "interval", seconds=POLL_INTERVAL, id="septa_pipeline")
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        sys.exit(0)
