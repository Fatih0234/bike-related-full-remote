"""Ingestion package."""

from erp.ingestion.fetch_open311 import fetch_window
from erp.ingestion.quality_gate import evaluate

__all__ = ["fetch_window", "evaluate"]
