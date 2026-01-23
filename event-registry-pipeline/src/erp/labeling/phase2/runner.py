"""Phase 2 runner (skeleton)."""

from __future__ import annotations

from typing import Optional

from erp.utils.logging import get_logger


logger = get_logger(__name__)


def run(limit: Optional[int] = None, dry_run: bool = False) -> None:
    """Run Phase 2 labeling (issue categorization)."""
    logger.info("phase2.run.start", extra={"limit": limit, "dry_run": dry_run})
    # TODO: query bike-related events, load prompt, call model, write labels.
    logger.info("phase2.run.complete", extra={"labeled": 0})
