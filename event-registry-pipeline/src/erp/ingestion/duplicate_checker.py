"""Database-backed duplicate checker for strict submissions."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from psycopg import Cursor

from erp.config import Settings
from erp.ingestion.quality_gate import DuplicateKey


class DatabaseDuplicateChecker:
    """Check strict duplicates against the canonical events table."""

    def __init__(self, cursor: Cursor, settings: Optional[Settings] = None) -> None:
        self.cursor = cursor
        self.settings = settings or Settings()

    def find_duplicate(self, key: DuplicateKey, requested_at: datetime) -> Optional[str]:
        window = timedelta(hours=self.settings.duplicate_window_hours)
        start = requested_at - window
        end = requested_at + window

        # Normalize description: strip URLs first, then collapse whitespace, then lowercase
        # This matches the Python normalize_for_dedupe() function in utils/text.py
        conditions = [
            "requested_at between %s and %s",
            "round(lat::numeric, %s) = %s",
            "round(lon::numeric, %s) = %s",
            "lower(regexp_replace(regexp_replace(coalesce(description, ''), 'https?://[^\\s]+', '', 'g'), '\\s+', ' ', 'g')) = %s",
        ]
        params: list[object] = [
            start,
            end,
            self.settings.duplicate_coord_precision,
            key.lat_round,
            self.settings.duplicate_coord_precision,
            key.lon_round,
            key.description,
        ]

        if self.settings.duplicate_require_service_name and key.service_name:
            conditions.append("service_name = %s")
            params.append(key.service_name)

        if self.settings.duplicate_require_address and key.address_string:
            conditions.append("address_string = %s")
            params.append(key.address_string)

        query = f"select service_request_id from events where {' and '.join(conditions)} limit 1"

        self.cursor.execute(query, params)
        row = self.cursor.fetchone()
        if row:
            return row[0]
        return None
