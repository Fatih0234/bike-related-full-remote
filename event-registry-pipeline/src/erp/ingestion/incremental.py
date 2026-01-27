"""Helpers for service_request_id-based incremental ingestion."""

from __future__ import annotations

from typing import Iterable, List, Optional

from erp.utils.time import parse_service_request_id


def compute_gap_ids(
    last_sequence: Optional[int],
    max_sequence: Optional[int],
    year: int,
) -> List[str]:
    """Compute missing service_request_id values for a year."""
    if max_sequence is None:
        return []

    start = (last_sequence or 0) + 1
    if start > max_sequence:
        return []

    return [f"{seq}-{year}" for seq in range(start, max_sequence + 1)]


def max_sequence_for_year(service_request_ids: Iterable[str], year: int) -> Optional[int]:
    """Return max sequence number for a given year from IDs."""
    sequences: list[int] = []
    for srid in service_request_ids:
        sr_year, sequence = parse_service_request_id(srid)
        if sr_year == year and sequence is not None:
            sequences.append(sequence)

    return max(sequences) if sequences else None
