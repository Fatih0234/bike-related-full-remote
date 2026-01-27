"""Ingestion package."""

from erp.ingestion.fetch_open311 import fetch_window
from erp.ingestion.incremental import compute_gap_ids, max_sequence_for_year
from erp.ingestion.quality_gate import evaluate

__all__ = ["fetch_window", "evaluate", "compute_gap_ids", "max_sequence_for_year"]
