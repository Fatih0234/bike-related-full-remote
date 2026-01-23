"""Quality gate for incoming events (skeleton)."""

from __future__ import annotations

from erp.models import AcceptDecision, CanonicalEvent, RawEvent, RejectDecision
from erp.utils.text import extract_media_path
from erp.utils.time import parse_service_request_id


def evaluate(raw_event: RawEvent) -> AcceptDecision | RejectDecision:
    """Evaluate a raw event and return accept/reject decision."""
    if not raw_event.service_request_id:
        return RejectDecision(raw_event=raw_event, reason="missing_service_request_id")

    if raw_event.lat is None or raw_event.lon is None:
        return RejectDecision(raw_event=raw_event, reason="missing_coordinates")

    year, sequence = parse_service_request_id(raw_event.service_request_id)
    has_description = bool(raw_event.description and raw_event.description.strip())

    canonical = CanonicalEvent(
        service_request_id=raw_event.service_request_id,
        title=raw_event.title,
        description=raw_event.description,
        requested_at=raw_event.requested_datetime,
        status=raw_event.status,
        lat=raw_event.lat,
        lon=raw_event.lon,
        address_string=raw_event.address_string,
        service_name=raw_event.service_name,
        media_path=extract_media_path(raw_event.media_url),
        year=year,
        sequence_number=sequence,
        has_description=has_description,
        skip_llm=not has_description,
    )

    # TODO: apply category mapping and richer rejection rules.
    return AcceptDecision(raw_event=raw_event, normalized=canonical)
