"""Phase 1 runner (skeleton)."""

from __future__ import annotations

from typing import Optional

from erp.utils.logging import get_logger


logger = get_logger(__name__)


def run(limit: Optional[int] = None, dry_run: bool = False) -> None:
    """Run Phase 1 labeling (bike-related classification)."""
    logger.info("phase1.run.start", extra={"limit": limit, "dry_run": dry_run})
    # TODO: query events needing Phase 1, load prompt, call model, write labels.
    logger.info("phase1.run.complete", extra={"labeled": 0})
