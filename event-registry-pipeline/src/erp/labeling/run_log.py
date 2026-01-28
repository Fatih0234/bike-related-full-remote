"""Labeling run logging helpers."""

from __future__ import annotations

from typing import Optional

from psycopg import Cursor
from psycopg.types.json import Jsonb


def create_run(
    cursor: Cursor,
    phase: str,
    model: str,
    prompt_version: str,
    dry_run: bool,
    requested_limit: int | None,
) -> int:
    cursor.execute(
        "insert into public.labeling_runs (phase, model, prompt_version, dry_run, requested_limit) "
        "values (%s, %s, %s, %s, %s) returning label_run_id",
        (phase, model, prompt_version, dry_run, requested_limit),
    )
    return int(cursor.fetchone()[0])


def set_selected_count(cursor: Cursor, label_run_id: int, selected_count: int) -> None:
    cursor.execute(
        "update public.labeling_runs set selected_count = %s where label_run_id = %s",
        (selected_count, label_run_id),
    )


def complete_run_success(
    cursor: Cursor,
    label_run_id: int,
    attempted_count: int,
    inserted_count: int,
    skipped_count: int,
    failed_count: int,
    first_labeled_service_request_id: str | None = None,
    last_labeled_service_request_id: str | None = None,
    min_labeled_requested_at: object | None = None,
    max_labeled_requested_at: object | None = None,
) -> None:
    cursor.execute(
        "update public.labeling_runs set status = 'success', finished_at = now(), "
        "attempted_count = %s, inserted_count = %s, skipped_count = %s, failed_count = %s, "
        "first_labeled_service_request_id = %s, last_labeled_service_request_id = %s, "
        "min_labeled_requested_at = %s, max_labeled_requested_at = %s "
        "where label_run_id = %s",
        (
            attempted_count,
            inserted_count,
            skipped_count,
            failed_count,
            first_labeled_service_request_id,
            last_labeled_service_request_id,
            min_labeled_requested_at,
            max_labeled_requested_at,
            label_run_id,
        ),
    )


def complete_run_failed(
    cursor: Cursor,
    label_run_id: int,
    error: Exception,
    attempted_count: Optional[int] = None,
) -> None:
    cursor.execute(
        "update public.labeling_runs set status = 'failed', finished_at = now(), "
        "attempted_count = %s, error_json = %s where label_run_id = %s",
        (
            attempted_count,
            Jsonb({"error": str(error)}),
            label_run_id,
        ),
    )

