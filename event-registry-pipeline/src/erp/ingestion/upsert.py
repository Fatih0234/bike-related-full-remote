"""Database write helpers (skeleton)."""

from __future__ import annotations

from typing import Iterable

from erp.models import AcceptDecision, RawEvent, RejectDecision
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def write_raw(run_id: str, raw_events: Iterable[RawEvent], dry_run: bool = False) -> int:
    """Write raw events to events_raw."""
    count = len(list(raw_events))
    if dry_run:
        logger.info("write_raw.dry_run", extra={"run_id": run_id, "count": count})
        return count

    # TODO: implement bulk insert into events_raw
    logger.warning("write_raw.not_implemented", extra={"run_id": run_id, "count": count})
    return 0


def write_rejected(
    run_id: str,
    rejects: Iterable[RejectDecision],
    dry_run: bool = False,
) -> int:
    """Write rejected events to events_rejected."""
    count = len(list(rejects))
    if dry_run:
        logger.info("write_rejected.dry_run", extra={"run_id": run_id, "count": count})
        return count

    # TODO: implement bulk insert into events_rejected
    logger.warning("write_rejected.not_implemented", extra={"run_id": run_id, "count": count})
    return 0


def upsert_events(
    run_id: str,
    accepts: Iterable[AcceptDecision],
    dry_run: bool = False,
) -> int:
    """Upsert accepted events into events."""
    count = len(list(accepts))
    if dry_run:
        logger.info("upsert_events.dry_run", extra={"run_id": run_id, "count": count})
        return count

    # TODO: implement UPSERT into events
    logger.warning("upsert_events.not_implemented", extra={"run_id": run_id, "count": count})
    return 0
