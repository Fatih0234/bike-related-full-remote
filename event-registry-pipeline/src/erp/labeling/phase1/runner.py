"""Phase 1 runner (bike-related labeling)."""

from __future__ import annotations

import hashlib
from typing import Optional

from erp.config import Settings
from erp.db.client import db_cursor
from erp.labeling.common.prompt_loader import load_prompt
from erp.labeling.common.schemas import (
    Phase1Output,
    bike_related_from_label,
    truncate_evidence,
    truncate_reasoning,
)
from erp.labeling.llm.gemini import GeminiClient
from erp.utils.logging import get_logger


logger = get_logger(__name__)


def _llm_input(title: Optional[str], description_redacted: Optional[str]) -> str:
    title_text = (title or "").strip()
    desc_text = (description_redacted or "").strip()
    return f"{title_text}\n\n{desc_text}"


def _input_hash(llm_input: str) -> str:
    return hashlib.md5(llm_input.encode("utf-8")).hexdigest()


def run(
    limit: Optional[int] = None,
    dry_run: bool = False,
    prompt_version: Optional[str] = None,
    model_id: Optional[str] = None,
) -> None:
    """Run Phase 1 labeling (bike-related classification)."""
    settings = Settings()
    prompt_version = prompt_version or settings.phase1_prompt_version
    model_id = model_id or settings.gemini_model_id

    prompt = load_prompt(phase=1, prompt_version=prompt_version)
    client = GeminiClient(settings)

    logger.info(
        "phase1.run.start",
        extra={"limit": limit, "dry_run": dry_run, "prompt_version": prompt_version, "model": model_id},
    )

    label_run_id: int | None = None
    rows: list[tuple[str, Optional[str], Optional[str], object, int, int]] = []
    # Default behavior: only label events that have never received any Phase 1 label row.
    # This prevents re-labeling the historical (legacy) dataset.
    select_sql = """
        select
          e.service_request_id,
          e.title,
          e.description_redacted,
          e.requested_at,
          e.year,
          e.sequence_number
        from public.events e
        where e.skip_llm = false
          and e.has_description = true
          and not exists (
            select 1
            from public.event_phase1_labels l
            where l.service_request_id = e.service_request_id
          )
        order by e.requested_at desc
    """
    if limit is not None:
        select_sql += " limit %s"

    from erp.labeling.run_log import complete_run_failed, complete_run_success, create_run, set_selected_count

    try:
        with db_cursor(settings) as cursor:
            label_run_id = create_run(
                cursor,
                phase="phase1",
                model=model_id,
                prompt_version=prompt_version,
                dry_run=dry_run,
                requested_limit=limit,
            )

        with db_cursor(settings) as cursor:
            cursor.execute(select_sql, (limit,) if limit is not None else ())
            rows = list(cursor.fetchall())

        with db_cursor(settings) as cursor:
            set_selected_count(cursor, label_run_id, len(rows))

        if not rows:
            logger.info("phase1.run.no_candidates", extra={"label_run_id": label_run_id})
            with db_cursor(settings) as cursor:
                complete_run_success(
                    cursor,
                    label_run_id=label_run_id,
                    attempted_count=0,
                    inserted_count=0,
                    skipped_count=0,
                    failed_count=0,
                )
            logger.info("phase1.run.complete", extra={"labeled": 0, "dry_run": dry_run, "label_run_id": label_run_id})
            return

        inserted = 0
        skipped = 0
        failures = 0
        attempted = 0
        inserted_id_frontier: tuple[int, int, str] | None = None  # (year, seq, srid) min
        inserted_id_frontier_max: tuple[int, int, str] | None = None  # (year, seq, srid) max
        min_requested_at: object | None = None
        max_requested_at: object | None = None

        for service_request_id, title, description_redacted, requested_at, year, sequence_number in rows:
            llm_input = _llm_input(title=title, description_redacted=description_redacted)
            if not llm_input:
                skipped += 1
                continue

            attempted += 1
            full_prompt = f"{prompt}\n\nINPUT:\n{llm_input}\n"
            output, latency_ms, attempts, error = client.generate_structured(full_prompt, Phase1Output)

            if output is None:
                failures += 1
                logger.warning(
                    "phase1.label.failed",
                    extra={
                        "label_run_id": label_run_id,
                        "service_request_id": service_request_id,
                        "attempts": attempts,
                        "latency_ms": latency_ms,
                        "error": error,
                    },
                )
                continue

            bike_related = bike_related_from_label(output.label)
            evidence = truncate_evidence(output.evidence)
            reasoning = truncate_reasoning(output.reasoning)
            confidence = float(output.confidence)
            input_hash = _input_hash(llm_input)

            logger.info(
                "phase1.label.ok",
                extra={
                    "label_run_id": label_run_id,
                    "service_request_id": service_request_id,
                    "label": output.label,
                    "bike_related": bike_related,
                    "confidence": confidence,
                    "attempts": attempts,
                    "latency_ms": latency_ms,
                    "dry_run": dry_run,
                },
            )

            if dry_run:
                inserted += 1
                continue

            insert_sql = """
                insert into public.event_phase1_labels (
                    service_request_id,
                    model,
                    prompt_version,
                    input_hash,
                    bike_related,
                    confidence,
                    evidence,
                    reasoning
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (service_request_id, prompt_version, input_hash) do nothing
            """
            with db_cursor(settings) as cursor:
                cursor.execute(
                    insert_sql,
                    (
                        service_request_id,
                        model_id,
                        prompt_version,
                        input_hash,
                        bike_related,
                        confidence,
                        evidence,
                        reasoning,
                    ),
                )
                inserted_now = cursor.rowcount or 0

            if inserted_now:
                inserted += 1
                key = (int(year), int(sequence_number), service_request_id)
                if inserted_id_frontier is None or key < inserted_id_frontier:
                    inserted_id_frontier = key
                if inserted_id_frontier_max is None or key > inserted_id_frontier_max:
                    inserted_id_frontier_max = key
                if min_requested_at is None or requested_at < min_requested_at:
                    min_requested_at = requested_at
                if max_requested_at is None or requested_at > max_requested_at:
                    max_requested_at = requested_at
            else:
                skipped += 1

        logger.info(
            "phase1.run.complete",
            extra={
                "labeled": inserted,
                "skipped": skipped,
                "failures": failures,
                "dry_run": dry_run,
                "label_run_id": label_run_id,
            },
        )

        first_id = inserted_id_frontier[2] if inserted_id_frontier else None
        last_id = inserted_id_frontier_max[2] if inserted_id_frontier_max else None
        with db_cursor(settings) as cursor:
            complete_run_success(
                cursor,
                label_run_id=label_run_id,
                attempted_count=attempted,
                inserted_count=inserted,
                skipped_count=skipped,
                failed_count=failures,
                first_labeled_service_request_id=first_id,
                last_labeled_service_request_id=last_id,
                min_labeled_requested_at=min_requested_at,
                max_labeled_requested_at=max_requested_at,
            )
    except Exception as exc:
        logger.error("phase1.run.failed: %s", exc, extra={"label_run_id": label_run_id})
        if label_run_id is not None:
            with db_cursor(settings) as cursor:
                complete_run_failed(cursor, label_run_id=label_run_id, error=exc, attempted_count=None)
        raise
