import os

import pytest

from erp.ingestion.fetch_open311 import fetch_by_id, fetch_window


pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_API_TESTS"),
    reason="Set RUN_LIVE_API_TESTS=1 to run live API tests",
)


def test_fetch_window_returns_events_or_skips():
    events = fetch_window(since="2025-01-01", until="2025-01-07")
    if not events:
        pytest.skip("No events returned for this window")

    assert events[0].service_request_id


def test_fetch_by_id_roundtrip():
    events = fetch_window(since="2025-01-01", until="2025-01-07")
    if not events:
        pytest.skip("No events returned for this window")

    event = events[0]
    fetched = fetch_by_id(event.service_request_id)
    assert fetched is not None
    assert fetched.service_request_id == event.service_request_id
