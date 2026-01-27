"""Time and ID parsing helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple


def parse_service_request_id(service_request_id: str) -> Tuple[int | None, int | None]:
    """Parse service_request_id into (year, sequence)."""
    if not service_request_id or "-" not in service_request_id:
        return None, None

    sequence_str, year_str = service_request_id.split("-", maxsplit=1)
    try:
        return int(year_str), int(sequence_str)
    except ValueError:
        return None, None


def parse_requested_at(value: Optional[str]) -> Optional[datetime]:
    """Parse Open311 requested_datetime into a datetime."""
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None
