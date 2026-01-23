"""Typer CLI entry point."""

from __future__ import annotations

from datetime import date
from typing import Optional

import typer

from erp.config import Settings
from erp.db.client import db_cursor
from erp.ingestion.runner import run_ingestion
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
) -> None:
    """Run ingestion for a date window."""
    run_ingestion(since=since, until=until, dry_run=dry_run)


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
) -> None:
    """Run Phase 1 bike-related labeling."""
    run_phase1(limit=limit, dry_run=dry_run)


@phase2_app.command("run")
def phase2_run(
    limit: Optional[int] = typer.Option(None, help="Max events to label"),
    dry_run: bool = typer.Option(False, help="Do not write to DB"),
) -> None:
    """Run Phase 2 issue categorization."""
    run_phase2(limit=limit, dry_run=dry_run)


@db_app.command("check")
def db_check() -> None:
    """Check database connectivity."""
    try:
        with db_cursor() as cursor:
            cursor.execute("select 1")
            logger.info("db.check.ok")
    except Exception as exc:
        logger.error("db.check.failed", extra={"error": str(exc)})
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
