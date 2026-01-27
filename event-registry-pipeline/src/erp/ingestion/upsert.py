"""Database write helpers (skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence, TypeVar

from psycopg import Cursor
from psycopg.types.json import Jsonb

from erp.db.client import db_cursor
from erp.models import AcceptDecision, RawEvent, RejectDecision
from erp.utils.text import extract_media_path
from erp.utils.time import parse_requested_at
from erp.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RawWriteResult:
    count: int
    raw_id_by_srid: dict[str, int]
    raw_id_by_event_id: dict[int, int]


@dataclass
class UpsertResult:
    total: int
    inserted: int
    updated: int


def write_raw(
    run_id: int,
    raw_events: Iterable[RawEvent],
    dry_run: bool = False,
    cursor: Optional[Cursor] = None,
) -> RawWriteResult:
    """Write raw events to events_raw."""
    events = list(raw_events)
    count = len(events)
    if dry_run:
        logger.info("write_raw.dry_run run_id=%s count=%s", run_id, count)
        return RawWriteResult(count=count, raw_id_by_srid={}, raw_id_by_event_id={})

    raw_id_by_srid: dict[str, int] = {}
    raw_id_by_event_id: dict[int, int] = {}
    if cursor is None:
        with db_cursor() as db_cur:
            raw_id_by_srid, raw_id_by_event_id = _insert_raw_batches(
                db_cur,
                run_id,
                events,
            )
    else:
        raw_id_by_srid, raw_id_by_event_id = _insert_raw_batches(
            cursor,
            run_id,
            events,
        )

    return RawWriteResult(
        count=count,
        raw_id_by_srid=raw_id_by_srid,
        raw_id_by_event_id=raw_id_by_event_id,
    )


def write_rejected(
    run_id: int,
    rejects: Iterable[RejectDecision],
    dry_run: bool = False,
    raw_id_by_srid: Optional[dict[str, int]] = None,
    raw_id_by_event_id: Optional[dict[int, int]] = None,
    cursor: Optional[Cursor] = None,
) -> int:
    """Write rejected events to events_rejected."""
    reject_list = list(rejects)
    count = len(reject_list)
    if dry_run:
        logger.info("write_rejected.dry_run run_id=%s count=%s", run_id, count)
        return count

    if not reject_list:
        return 0

    raw_lookup = raw_id_by_srid or {}
    event_lookup = raw_id_by_event_id or {}

    if cursor is None:
        with db_cursor() as db_cur:
            _insert_rejects(db_cur, run_id, reject_list, raw_lookup, event_lookup)
    else:
        _insert_rejects(cursor, run_id, reject_list, raw_lookup, event_lookup)

    return count


def upsert_events(
    run_id: int,
    accepts: Iterable[AcceptDecision],
    dry_run: bool = False,
    cursor: Optional[Cursor] = None,
) -> UpsertResult:
    """Upsert accepted events into events."""
    accept_list = [a for a in accepts if a.normalized is not None]
    count = len(accept_list)
    if dry_run:
        logger.info("upsert_events.dry_run run_id=%s count=%s", run_id, count)
        return UpsertResult(total=count, inserted=0, updated=0)

    if cursor is None:
        with db_cursor() as db_cur:
            return _upsert_events(db_cur, run_id, accept_list)

    return _upsert_events(cursor, run_id, accept_list)


def _insert_raw_batches(
    cursor: Cursor,
    run_id: int,
    events: list[RawEvent],
    batch_size: int = 500,
) -> tuple[dict[str, int], dict[int, int]]:
    raw_id_by_srid: dict[str, int] = {}
    raw_id_by_event_id: dict[int, int] = {}
    if not events:
        return raw_id_by_srid, raw_id_by_event_id

    columns = (
        "run_id",
        "service_request_id",
        "title",
        "description",
        "requested_at",
        "status",
        "lat",
        "lon",
        "address_string",
        "service_name",
        "media_path",
        "payload",
    )
    placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"

    for batch in _chunked(events, batch_size):
        values: list[object] = []
        for event in batch:
            values.extend(
                [
                    run_id,
                    event.service_request_id,
                    event.title,
                    event.description,
                    parse_requested_at(event.requested_datetime),
                    (event.status or "").lower() if event.status else None,
                    event.lat,
                    event.lon,
                    event.address_string,
                    event.service_name,
                    extract_media_path(event.media_url),
                    Jsonb(event.payload),
                ]
            )

        query = (
            f"insert into events_raw ({', '.join(columns)}) values "
            + ",".join([placeholders] * len(batch))
            + " returning raw_id, service_request_id"
        )
        cursor.execute(query, values)
        rows = cursor.fetchall()
        for event, (raw_id, service_request_id) in zip(batch, rows):
            raw_id_by_event_id[id(event)] = int(raw_id)
            if service_request_id:
                raw_id_by_srid[str(service_request_id)] = int(raw_id)

    return raw_id_by_srid, raw_id_by_event_id


def _insert_rejects(
    cursor: Cursor,
    run_id: int,
    rejects: list[RejectDecision],
    raw_id_by_srid: dict[str, int],
    raw_id_by_event_id: dict[int, int],
    batch_size: int = 500,
) -> None:
    if not rejects:
        return

    columns = (
        "run_id",
        "raw_id",
        "service_request_id",
        "accepted",
        "reject_reason",
        "reject_details",
    )
    placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"

    for batch in _chunked(rejects, batch_size):
        values: list[object] = []
        valid_count = 0
        for reject in batch:
            raw_id = raw_id_by_srid.get(reject.raw_event.service_request_id or "")
            if raw_id is None:
                raw_id = raw_id_by_event_id.get(id(reject.raw_event))
            if raw_id is None:
                logger.warning(
                    "write_rejected.skip_no_raw_id service_request_id=%s reason=%s",
                    reject.raw_event.service_request_id,
                    reject.reason,
                )
                continue
            valid_count += 1
            accepted = bool(reject.details.get("accepted", False))
            values.extend(
                [
                    run_id,
                    raw_id,
                    reject.raw_event.service_request_id,
                    accepted,
                    reject.reason,
                    Jsonb(reject.details),
                ]
            )

        if valid_count == 0:
            continue

        query = f"insert into events_rejected ({', '.join(columns)}) values " + ",".join(
            [placeholders] * valid_count
        )
        cursor.execute(query, values)


def _upsert_events(
    cursor: Cursor,
    run_id: int,
    accepts: list[AcceptDecision],
    batch_size: int = 500,
) -> UpsertResult:
    if not accepts:
        return UpsertResult(total=0, inserted=0, updated=0)

    columns = (
        "service_request_id",
        "title",
        "description",
        "description_redacted",
        "requested_at",
        "status",
        "lat",
        "lon",
        "address_string",
        "service_name",
        "category",
        "subcategory",
        "subcategory2",
        "media_path",
        "year",
        "sequence_number",
        "has_description",
        "has_media",
        "skip_llm",
        "is_link_only",
        "is_flagged_abuse",
        "last_seen_at",
        "last_run_id",
    )
    placeholders = "(" + ",".join(["%s"] * len(columns)) + ")"
    total_inserted = 0
    total_updated = 0

    now = datetime.now(timezone.utc)
    for batch in _chunked(accepts, batch_size):
        values: list[object] = []
        for accept in batch:
            event = accept.normalized
            if event is None:
                continue
            values.extend(
                [
                    event.service_request_id,
                    event.title,
                    event.description,
                    event.description_redacted,
                    event.requested_at,
                    event.status,
                    event.lat,
                    event.lon,
                    event.address_string,
                    event.service_name,
                    event.category,
                    event.subcategory,
                    event.subcategory2,
                    event.media_path,
                    event.year,
                    event.sequence_number,
                    event.has_description,
                    event.has_media,
                    event.skip_llm,
                    event.is_link_only,
                    event.is_flagged_abuse,
                    now,
                    run_id,
                ]
            )

        query = (
            f"insert into events ({', '.join(columns)}) values "
            + ",".join([placeholders] * len(batch))
            + " on conflict (service_request_id) do update set "
            + "title = excluded.title, "
            + "description = excluded.description, "
            + "description_redacted = excluded.description_redacted, "
            + "requested_at = excluded.requested_at, "
            + "status = excluded.status, "
            + "lat = excluded.lat, "
            + "lon = excluded.lon, "
            + "address_string = excluded.address_string, "
            + "service_name = excluded.service_name, "
            + "category = excluded.category, "
            + "subcategory = excluded.subcategory, "
            + "subcategory2 = excluded.subcategory2, "
            + "media_path = excluded.media_path, "
            + "year = excluded.year, "
            + "sequence_number = excluded.sequence_number, "
            + "has_description = excluded.has_description, "
            + "has_media = excluded.has_media, "
            + "skip_llm = excluded.skip_llm, "
            + "is_link_only = excluded.is_link_only, "
            + "is_flagged_abuse = excluded.is_flagged_abuse, "
            + "last_seen_at = excluded.last_seen_at, "
            + "last_run_id = excluded.last_run_id "
            + "returning (xmax = 0) as inserted"
        )
        cursor.execute(query, values)
        results = cursor.fetchall()
        inserted = sum(1 for row in results if row[0])
        total_inserted += inserted
        total_updated += len(results) - inserted

    return UpsertResult(
        total=total_inserted + total_updated, inserted=total_inserted, updated=total_updated
    )


T = TypeVar("T")


def _chunked(items: Sequence[T], batch_size: int) -> list[list[T]]:
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]
