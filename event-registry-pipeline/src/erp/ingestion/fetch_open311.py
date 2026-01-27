"""Open311 fetcher."""

from __future__ import annotations

from typing import List, Optional

import time

import httpx

from erp.config import Settings
from erp.models import RawEvent
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def fetch_window(
    since: str,
    until: str,
    settings: Optional[Settings] = None,
) -> List[RawEvent]:
    """Fetch a date window from the Open311 API."""
    settings = settings or Settings()
    logger.info("fetch_window.start", extra={"since": since, "until": until})

    url = f"{settings.open311_base_url}/requests.json"
    page = 1
    events: List[RawEvent] = []

    with httpx.Client(timeout=settings.open311_timeout_seconds) as client:
        while True:
            params: dict[str, str | int] = {
                "start_date": since,
                "end_date": until,
                "page": page,
            }
            if settings.open311_use_extensions:
                params["extensions"] = "true"

            response = _get_with_retry(
                client,
                url,
                params=params,
                retries=settings.open311_max_retries,
            )
            response.raise_for_status()
            payload = response.json()

            if not payload:
                break

            for item in payload:
                events.append(_to_raw_event(item))

            if len(payload) < settings.open311_page_size:
                break

            page += 1

    logger.info("fetch_window.complete count=%s", len(events))
    return events


def fetch_by_id(
    service_request_id: str,
    settings: Optional[Settings] = None,
) -> Optional[RawEvent]:
    """Fetch a single Open311 record by service_request_id.

    Used for ID-gap filling based on sequence numbers.
    """
    settings = settings or Settings()
    url = f"{settings.open311_base_url}/requests/{service_request_id}.json"

    try:
        with httpx.Client(timeout=settings.open311_timeout_seconds) as client:
            response = _get_with_retry(
                client,
                url,
                params=None,
                retries=settings.open311_max_retries,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("fetch_by_id.failed", extra={"id": service_request_id, "error": str(exc)})
        return None

    if not payload:
        return None

    return _to_raw_event(payload[0])


def _to_raw_event(payload: dict) -> RawEvent:
    """Convert API payload into RawEvent with attached payload."""
    return RawEvent.model_validate({**payload, "payload": payload})


def _get_with_retry(
    client: httpx.Client,
    url: str,
    params: Optional[dict] = None,
    retries: int = 3,
) -> httpx.Response:
    """GET with simple retry and backoff."""
    attempt = 0
    while True:
        try:
            response = client.get(url, params=params)
            if response.status_code >= 500 and attempt < retries:
                attempt += 1
                time.sleep(min(2**attempt, 8))
                continue
            return response
        except httpx.RequestError:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(min(2**attempt, 8))
