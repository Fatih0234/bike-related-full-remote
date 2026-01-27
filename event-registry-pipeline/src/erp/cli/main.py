"""Typer CLI entry point."""

from __future__ import annotations

from datetime import date, timedelta, timezone, datetime
from typing import Optional

import typer

from erp.config import Settings
from erp.db.client import db_cursor
from erp.ingestion.runner import run_ingestion
from erp.utils.time import parse_requested_at
from erp.labeling.phase1.runner import run as run_phase1
from erp.labeling.phase2.runner import run as run_phase2
from erp.utils.logging import configure_logging, get_logger


app = typer.Typer(help="Event Registry Pipeline CLI")
ingest_app = typer.Typer(help="Ingestion commands")
phase1_app = typer.Typer(help="Phase 1 labeling commands")
phase2_app = typer.Typer(help="Phase 2 labeling commands")
db_app = typer.Typer(help="Database utilities")

app.add_typer(ingest_app, name="ingest")
app.add_typer(phase1_app, name="phase1")
app.add_typer(phase2_app, name="phase2")
app.add_typer(db_app, name="db")

logger = get_logger(__name__)


@app.callback()
def main() -> None:
    """Initialize logging for all commands."""
    settings = Settings()
    configure_logging(settings.log_level)


@ingest_app.command("run")
def ingest_run(
    since: str = typer.Option(..., help="Start date (YYYY-MM-DD)"),
    until: str = typer.Option(..., help="End date (YYYY-MM-DD)"),
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
    gap_fill_limit: Optional[int] = typer.Option(
        None, help="Max gap-fill IDs to fetch (overrides env)"
    ),
    no_gap_fill: bool = typer.Option(False, help="Disable gap-fill for this run"),
) -> None:
    """Run ingestion for a date window."""
    run_ingestion(
        since=since,
        until=until,
        dry_run=dry_run,
        gap_fill_limit=gap_fill_limit,
        enable_gap_fill=not no_gap_fill,
    )


@ingest_app.command("auto")
def ingest_auto(
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
    lookback_days: int = typer.Option(
        2, help="Fallback lookback when no successful runs exist"
    ),
    no_gap_fill: bool = typer.Option(False, help="Disable gap-fill for this run"),
    gap_fill_limit: Optional[int] = typer.Option(
        None, help="Max gap-fill IDs to fetch (overrides env)"
    ),
) -> None:
    """Run ingestion using a DB-derived window (for cron)."""
    settings = Settings()

    today = datetime.now(timezone.utc).date()
    until_date = (today + timedelta(days=1)).isoformat()
    since_date: str | None = None

    try:
        with db_cursor(settings) as cursor:
            cursor.execute(
                "select fetch_window_end from public.pipeline_runs "
                "where status = 'success' and fetch_window_end is not null "
                "order by finished_at desc nulls last, run_id desc limit 1"
            )
            row = cursor.fetchone()
        if row and row[0]:
            fetch_end = row[0]
            if isinstance(fetch_end, str):
                parsed = parse_requested_at(fetch_end)
                fetch_end_dt = parsed if parsed is not None else None
            else:
                fetch_end_dt = fetch_end
            if fetch_end_dt is not None:
                # `erp ingest auto` uses an "until = tomorrow" policy (date-only API).
                # If this command runs more than once per day, the previous run's
                # fetch_window_end can be tomorrow, which would incorrectly push
                # `since` into the future. Clamp to today to keep the window sane.
                since_date = min(fetch_end_dt.date(), today).isoformat()
    except Exception as exc:
        logger.warning("ingest.auto.last_success_lookup_failed: %s", exc)

    if since_date is None:
        since_date = (today - timedelta(days=lookback_days)).isoformat()

    run_ingestion(
        since=since_date,
        until=until_date,
        dry_run=dry_run,
        gap_fill_limit=gap_fill_limit,
        enable_gap_fill=not no_gap_fill,
    )


@ingest_app.command("backfill")
def ingest_backfill(
    year: int = typer.Option(..., help="Year to backfill"),
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
) -> None:
    """Backfill a full year using ID-based fetches (skeleton)."""
    start = date(year, 1, 1).isoformat()
    end = date(year, 12, 31).isoformat()
    logger.info("backfill.start", extra={"year": year})
    run_ingestion(since=start, until=end, dry_run=dry_run)


@phase1_app.command("run")
def phase1_run(
    limit: Optional[int] = typer.Option(None, help="Max events to label"),
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
    prompt_version: Optional[str] = typer.Option(
        None, help="Prompt version (default from PHASE1_PROMPT_VERSION)"
    ),
    model_id: Optional[str] = typer.Option(None, help="Model ID (default from GEMINI_MODEL_ID)"),
) -> None:
    """Run Phase 1 bike-related labeling."""
    run_phase1(limit=limit, dry_run=dry_run, prompt_version=prompt_version, model_id=model_id)


@phase2_app.command("run")
def phase2_run(
    limit: Optional[int] = typer.Option(None, help="Max events to label"),
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
    prompt_version: Optional[str] = typer.Option(
        None, help="Prompt version (default from PHASE2_PROMPT_VERSION)"
    ),
    model_id: Optional[str] = typer.Option(None, help="Model ID (default from GEMINI_MODEL_ID)"),
) -> None:
    """Run Phase 2 issue categorization."""
    run_phase2(limit=limit, dry_run=dry_run, prompt_version=prompt_version, model_id=model_id)


@db_app.command("check")
def db_check() -> None:
    """Check database connectivity."""
    try:
        with db_cursor() as cursor:
            cursor.execute("select 1")
            logger.info("db.check.ok")
    except Exception as exc:
        logger.error("db.check.failed: %s", exc)
        typer.echo(f"Database check failed: {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
