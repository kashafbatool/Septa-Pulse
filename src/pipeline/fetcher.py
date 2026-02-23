"""SEPTA Open Data API client.

Fetches real-time vehicle positions and alerts with automatic retry logic.
"""

import logging
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SEPTA_API_BASE = os.getenv("SEPTA_API_BASE", "https://www3.septa.org/api")
_DEFAULT_TIMEOUT = 10
_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds


class SEPTAAPIError(Exception):
    pass


def _get(url: str, params: dict | None = None) -> Any:
    """HTTP GET with exponential backoff retry."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=_DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %d: %s", attempt, url)
        except requests.exceptions.HTTPError as exc:
            logger.warning(
                "HTTP %s on attempt %d: %s", exc.response.status_code, attempt, url
            )
        except requests.exceptions.RequestException as exc:
            logger.warning("Request error on attempt %d: %s — %s", attempt, url, exc)

        if attempt < _MAX_RETRIES:
            sleep = _BACKOFF_BASE**attempt
            logger.debug("Retrying in %ds...", sleep)
            time.sleep(sleep)

    raise SEPTAAPIError(f"Failed to fetch {url} after {_MAX_RETRIES} attempts")


class SEPTAClient:
    """Client for the SEPTA Open Data API."""

    def __init__(self, base_url: str = SEPTA_API_BASE) -> None:
        self.base_url = base_url.rstrip("/")

    def get_all_buses(self) -> list[dict]:
        """Return all active bus and trolley positions via TransitViewAll."""
        url = f"{self.base_url}/TransitViewAll/index.php"
        data = _get(url)
        # Response shape: {"bus": [...]}
        if isinstance(data, dict):
            buses = data.get("bus", [])
            if not buses:
                # Log top-level keys so we can detect format changes
                logger.info(
                    "TransitViewAll keys: %s | counts: %s",
                    list(data.keys()),
                    {k: len(v) for k, v in data.items() if isinstance(v, list)},
                )
            return buses
        logger.warning("TransitViewAll unexpected response type: %s", type(data))
        return []

    def get_train_positions(self) -> list[dict]:
        """Return all active regional rail train positions via TrainView."""
        url = f"{self.base_url}/TrainView/index.php"
        data = _get(url)
        if isinstance(data, list):
            return data
        return []

    def get_alerts(self) -> list[dict]:
        """Return all current service alerts."""
        url = f"{self.base_url}/Alerts/index.php"
        data = _get(url, params={"req1": "all"})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
        return []
