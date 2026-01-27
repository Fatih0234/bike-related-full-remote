"""Ingestion runner."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import List

from erp.config import Settings
from erp.db.client import db_cursor
from erp.ingestion.duplicate_checker import DatabaseDuplicateChecker
from erp.ingestion.fetch_open311 import fetch_by_id, fetch_window
from erp.ingestion.incremental import compute_gap_ids, max_sequence_for_year
from erp.ingestion.quality_gate import QualityGate, load_category_map
from erp.ingestion.run_log import create_run, complete_run_failed, complete_run_success
from erp.ingestion.upsert import write_raw, write_rejected, upsert_events
from erp.models import AcceptDecision, RawEvent, RejectDecision
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def run_ingestion(
    since: str,
    until: str,
    dry_run: bool = False,
    gap_fill_limit: int | None = None,
    enable_gap_fill: bool | None = None,
) -> None:
    """Run ingestion for a date window."""
    settings = Settings()
    run_id_db: int | None = None
    run_id_log = str(uuid.uuid4()) if dry_run else "pending"

    # Apply overlap hours to extend the fetch window backwards
    # This helps catch events that may have been missed at window boundaries
    if settings.ingestion_overlap_hours > 0:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        since_with_overlap = since_dt - timedelta(hours=settings.ingestion_overlap_hours)
        fetch_since = since_with_overlap.strftime("%Y-%m-%d")
    else:
        fetch_since = since

    logger.info(
        "ingestion.start run_id=%s since=%s until=%s fetch_since=%s overlap_hours=%s",
        run_id_log,
        since,
        until,
        fetch_since,
        settings.ingestion_overlap_hours,
    )

    if not dry_run:
        with db_cursor(settings) as cursor:
            run_id_db = create_run(cursor, since, until)
        run_id_log = str(run_id_db)

    try:
        raw_events, missing_ids_404 = _fetch_with_gap_fill(
            fetch_since,
            until,
            settings,
            dry_run=dry_run,
            gap_fill_limit=gap_fill_limit,
            enable_gap_fill=enable_gap_fill,
        )
        logger.info("ingestion.fetched run_id=%s count=%s", run_id_log, len(raw_events))

        category_map = load_category_map()
        duplicate_checker = None
        if not dry_run:
            with db_cursor(settings) as cursor:
                duplicate_checker = DatabaseDuplicateChecker(cursor, settings)
                gate = QualityGate(
                    settings=settings,
                    category_map=category_map,
                    duplicate_checker=duplicate_checker,
                )
                decisions = [gate.evaluate(event) for event in raw_events]
        else:
            gate = QualityGate(settings=settings, category_map=category_map)
            decisions = [gate.evaluate(event) for event in raw_events]

        accepts: List[AcceptDecision] = [d for d in decisions if isinstance(d, AcceptDecision)]
        rejects: List[RejectDecision] = [d for d in decisions if isinstance(d, RejectDecision)]
        review_rejects: List[RejectDecision] = []
        for accept in accepts:
            if accept.review_reason:
                details = dict(accept.review_details)
                details.setdefault("accepted", True)
                review_rejects.append(
                    RejectDecision(
                        raw_event=accept.raw_event,
                        reason=accept.review_reason,
                        details=details,
                    )
                )
        rejects_all = rejects + review_rejects

        if dry_run:
            _log_dry_run_summary(raw_events, accepts, rejects, review_rejects)
            return

        if run_id_db is None:
            raise ValueError("run_id missing for database write")

        with db_cursor(settings) as cursor:
            raw_result = write_raw(run_id_db, raw_events, cursor=cursor)
            write_rejected(
                run_id_db,
                rejects_all,
                raw_id_by_srid=raw_result.raw_id_by_srid,
                raw_id_by_event_id=raw_result.raw_id_by_event_id,
                cursor=cursor,
            )
            upsert_result = upsert_events(run_id_db, accepts, cursor=cursor)

        true_reject_count = sum(
            1 for reject in rejects_all if not bool(reject.details.get("accepted", False))
        )
        with db_cursor(settings) as cursor:
            complete_run_success(
                cursor,
                run_id_db,
                fetched_count=len(raw_events),
                staged_count=raw_result.count,
                rejected_count=true_reject_count,
                inserted_count=upsert_result.inserted,
                updated_count=upsert_result.updated,
            )

        logger.info(
            "ingestion.complete run_id=%s raw=%s accepted=%s rejected=%s",
            run_id_log,
            len(raw_events),
            len(accepts),
            true_reject_count,
        )

    except Exception as exc:
        if not dry_run and run_id_db is not None:
            with db_cursor(settings) as cursor:
                complete_run_failed(cursor, run_id_db, exc, fetched_count=None)
        logger.exception("ingestion.failed run_id=%s", run_id_log)
        raise


def _fetch_with_gap_fill(
    since: str,
    until: str,
    settings: Settings,
    dry_run: bool,
    gap_fill_limit: int | None,
    enable_gap_fill: bool | None,
) -> tuple[List[RawEvent], int]:
    raw_events = fetch_window(since, until, settings)
    if enable_gap_fill is False:
        return raw_events, 0

    if enable_gap_fill is None and not settings.ingestion_enable_gap_fill:
        return raw_events, 0

    has_db = bool(settings.database_url or settings.pghost)
    if dry_run and not has_db:
        return raw_events, 0

    missing_id_events = [event for event in raw_events if not event.service_request_id]
    events_by_id = {
        event.service_request_id: event for event in raw_events if event.service_request_id
    }
    if not events_by_id:
        return raw_events, 0

    years = {int(srid.split("-")[1]) for srid in events_by_id.keys() if "-" in srid}
    if not years:
        return list(events_by_id.values()) + missing_id_events, 0

    last_sequences: dict[int, int | None] = {year: None for year in years}
    if has_db:
        with db_cursor(settings) as cursor:
            for year in years:
                cursor.execute("select max(sequence_number) from events where year = %s", (year,))
                row = cursor.fetchone()
                last_sequences[year] = row[0] if row else None

    missing_ids_404 = 0
    for year in years:
        max_seq = max_sequence_for_year(events_by_id.keys(), year)
        logger.info(
            "ingestion.gap_fill.range year=%s last_seq=%s max_seq=%s",
            year,
            last_sequences.get(year),
            max_seq,
        )
        gap_ids = compute_gap_ids(last_sequences.get(year), max_seq, year)
        limit = gap_fill_limit if gap_fill_limit is not None else settings.ingestion_gap_fill_limit
        if limit and len(gap_ids) > limit:
            gap_ids = gap_ids[:limit]

        if gap_ids:
            logger.info("ingestion.gap_fill year=%s count=%s", year, len(gap_ids))

        if not gap_ids:
            continue

        if settings.open311_max_workers > 1:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=settings.open311_max_workers) as executor:
                futures = {
                    executor.submit(fetch_by_id, service_request_id, settings): service_request_id
                    for service_request_id in gap_ids
                }
                for future in as_completed(futures):
                    fetched = future.result()
                    if fetched is None:
                        missing_ids_404 += 1
                        continue
                    if (
                        fetched.service_request_id
                        and fetched.service_request_id not in events_by_id
                    ):
                        events_by_id[fetched.service_request_id] = fetched
        else:
            for service_request_id in gap_ids:
                fetched = fetch_by_id(service_request_id, settings)
                if fetched is None:
                    missing_ids_404 += 1
                    continue
                if fetched.service_request_id and fetched.service_request_id not in events_by_id:
                    events_by_id[fetched.service_request_id] = fetched

    if missing_ids_404:
        logger.info("ingestion.gap_fill.missing_404 count=%s", missing_ids_404)

    return list(events_by_id.values()) + missing_id_events, missing_ids_404


def _log_dry_run_summary(
    raw_events: List[RawEvent],
    accepts: List[AcceptDecision],
    rejects: List[RejectDecision],
    review_rejects: List[RejectDecision],
) -> None:
    logger.info(
        "dry_run.summary fetched=%s accepted=%s rejected=%s review=%s",
        len(raw_events),
        len(accepts),
        len(rejects),
        len(review_rejects),
    )

    reason_counts = Counter(reject.reason for reject in rejects)
    for reason, count in reason_counts.items():
        logger.info("dry_run.reject reason=%s count=%s", reason, count)

    review_counts = Counter(reject.reason for reject in review_rejects)
    for reason, count in review_counts.items():
        logger.info("dry_run.review reason=%s count=%s", reason, count)

    for reject in (rejects + review_rejects)[:3]:
        logger.info("dry_run.reject_example reason=%s details=%s", reject.reason, reject.details)
