"""Open311 fetcher (skeleton)."""

from __future__ import annotations

from typing import List, Optional

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
    """Fetch a date window from the Open311 API.

    This is a skeleton implementation. It should be expanded to:
    - paginate with page size
    - handle timeouts/retries
    - return RawEvent models
    """
    settings = settings or Settings()
    logger.info("fetch_window.start", extra={"since": since, "until": until})

    # TODO: implement paging based on settings.open311_page_size
    # TODO: parse JSON into RawEvent models
    return []


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
            response = client.get(url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("fetch_by_id.failed", extra={"id": service_request_id, "error": str(exc)})
        return None

    if not payload:
        return None

    return RawEvent.model_validate({**payload[0], "payload": payload[0]})
