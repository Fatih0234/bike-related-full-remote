"""Ingestion runner (skeleton)."""

from __future__ import annotations

import uuid
from typing import List

from erp.ingestion.fetch_open311 import fetch_window
from erp.ingestion.quality_gate import evaluate
from erp.ingestion.upsert import upsert_events, write_raw, write_rejected
from erp.models import AcceptDecision, RawEvent, RejectDecision
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def run_ingestion(since: str, until: str, dry_run: bool = False) -> None:
    """Run ingestion for a date window (skeleton)."""
    run_id = str(uuid.uuid4())
    logger.info("ingestion.start", extra={"run_id": run_id, "since": since, "until": until})

    raw_events: List[RawEvent] = fetch_window(since, until)
    logger.info("ingestion.fetched", extra={"run_id": run_id, "count": len(raw_events)})

    decisions = [evaluate(event) for event in raw_events]
    accepts: List[AcceptDecision] = [d for d in decisions if isinstance(d, AcceptDecision)]
    rejects: List[RejectDecision] = [d for d in decisions if isinstance(d, RejectDecision)]

    write_raw(run_id, raw_events, dry_run=dry_run)
    write_rejected(run_id, rejects, dry_run=dry_run)
    upsert_events(run_id, accepts, dry_run=dry_run)

    logger.info(
        "ingestion.complete",
        extra={
            "run_id": run_id,
            "raw": len(raw_events),
            "accepted": len(accepts),
            "rejected": len(rejects),
            "dry_run": dry_run,
        },
    )
