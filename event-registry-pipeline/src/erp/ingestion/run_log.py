"""Pipeline run logging helpers."""

from __future__ import annotations

from typing import Optional

from psycopg import Cursor
from psycopg.types.json import Jsonb


def create_run(cursor: Cursor, since: str, until: str) -> int:
    cursor.execute(
        "insert into pipeline_runs (status, fetch_window_start, fetch_window_end) "
        "values ('running', %s, %s) returning run_id",
        (since, until),
    )
    return int(cursor.fetchone()[0])


def complete_run_success(
    cursor: Cursor,
    run_id: int,
    fetched_count: int,
    staged_count: int,
    rejected_count: int,
    inserted_count: int,
    updated_count: int,
) -> None:
    cursor.execute(
        "update pipeline_runs set status = 'success', finished_at = now(), "
        "fetched_count = %s, staged_count = %s, rejected_count = %s, "
        "inserted_count = %s, updated_count = %s where run_id = %s",
        (
            fetched_count,
            staged_count,
            rejected_count,
            inserted_count,
            updated_count,
            run_id,
        ),
    )


def complete_run_failed(
    cursor: Cursor,
    run_id: int,
    error: Exception,
    fetched_count: Optional[int] = None,
) -> None:
    cursor.execute(
        "update pipeline_runs set status = 'failed', finished_at = now(), "
        "fetched_count = %s, error_json = %s where run_id = %s",
        (
            fetched_count,
            Jsonb({"error": str(error)}),
            run_id,
        ),
    )
