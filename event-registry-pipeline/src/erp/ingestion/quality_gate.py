"""Quality gate for incoming events."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol

from erp.config import Settings
from erp.models import AcceptDecision, CanonicalEvent, RawEvent, RejectDecision
from erp.utils.text import extract_media_path, is_link_only, normalize_for_dedupe
from erp.utils.time import parse_requested_at, parse_service_request_id


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = PROJECT_ROOT / "data" / "sags_uns_categories_3level.csv"

SPAM_TERMS = {
    "test",
    "asdf",
    "asdfasdf",
    "qwerty",
    "1234",
}


@dataclass(frozen=True)
class DuplicateKey:
    """Key for strict duplicate detection."""

    description: str
    lat_round: float
    lon_round: float
    service_name: Optional[str]
    address_string: Optional[str]


@dataclass
class DuplicateEntry:
    """Tracked duplicate entry for in-run checks."""

    service_request_id: str
    requested_at: datetime


class DuplicateChecker(Protocol):
    """Protocol for checking duplicates against the database."""

    def find_duplicate(self, key: DuplicateKey, requested_at: datetime) -> Optional[str]:
        """Return existing service_request_id if duplicate is found."""


def load_category_map(csv_path: Path = DATA_PATH) -> dict[str, dict[str, Optional[str]]]:
    """Load service_name -> category hierarchy mapping."""
    mapping: dict[str, dict[str, Optional[str]]] = {}

    if not csv_path.exists():
        raise FileNotFoundError(f"Category mapping not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row["subcategory2"] == "none":
                mapping[row["subcategory"]] = {
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "subcategory2": None,
                }
            else:
                mapping[row["subcategory2"]] = {
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "subcategory2": row["subcategory2"],
                }

    return mapping


class QualityGate:
    """Evaluate raw events and enforce ingestion rules."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        category_map: Optional[dict[str, dict[str, Optional[str]]]] = None,
        duplicate_checker: Optional[DuplicateChecker] = None,
    ) -> None:
        self.settings = settings or Settings()
        self.category_map = category_map or load_category_map()
        self.duplicate_checker = duplicate_checker
        self._seen: dict[DuplicateKey, list[DuplicateEntry]] = {}

    def evaluate(self, raw_event: RawEvent) -> AcceptDecision | RejectDecision:
        """Evaluate a raw event and return accept/reject decision."""
        if not raw_event.service_request_id:
            return RejectDecision(raw_event=raw_event, reason="missing_service_request_id")

        if not raw_event.requested_datetime:
            return RejectDecision(raw_event=raw_event, reason="missing_requested_at")

        requested_at = parse_requested_at(raw_event.requested_datetime)
        if requested_at is None:
            return RejectDecision(raw_event=raw_event, reason="invalid_requested_at")

        if raw_event.lat is None or raw_event.lon is None:
            return RejectDecision(raw_event=raw_event, reason="missing_coords")

        if not (-90 <= raw_event.lat <= 90 and -180 <= raw_event.lon <= 180):
            return RejectDecision(raw_event=raw_event, reason="invalid_coords")

        year, sequence = parse_service_request_id(raw_event.service_request_id)
        if year is None or sequence is None:
            return RejectDecision(raw_event=raw_event, reason="invalid_service_request_id")
        if not (2000 <= year <= 2100) or sequence <= 0:
            return RejectDecision(raw_event=raw_event, reason="invalid_service_request_id")

        if not raw_event.service_name:
            return RejectDecision(raw_event=raw_event, reason="missing_service_name")

        if not raw_event.title or not raw_event.title.strip():
            return RejectDecision(raw_event=raw_event, reason="missing_title")

        if not raw_event.address_string or not raw_event.address_string.strip():
            return RejectDecision(raw_event=raw_event, reason="missing_address_string")

        status = (raw_event.status or "").lower().strip()
        if status not in {"open", "closed"}:
            return RejectDecision(raw_event=raw_event, reason="invalid_status")

        category = self.category_map.get(raw_event.service_name)
        review_reason = None
        review_details: dict[str, object] = {}
        if category is None:
            category = {
                "category": "Unmapped",
                "subcategory": raw_event.service_name,
                "subcategory2": None,
            }
            review_reason = "unmapped_service_name"
            review_details = {"service_name": raw_event.service_name, "accepted": True}

        description = raw_event.description or ""
        has_description = bool(description.strip())
        link_only = has_description and is_link_only(
            description, min_chars=self.settings.link_only_min_chars
        )
        media_path = extract_media_path(raw_event.media_url)
        has_media = bool(media_path)
        skip_llm = (not has_description) or link_only

        if has_description:
            normalized = normalize_for_dedupe(description)
            if normalized in SPAM_TERMS:
                return RejectDecision(raw_event=raw_event, reason="spam_text")

        if has_description:
            duplicate_id = self._check_duplicate(
                raw_event,
                requested_at=requested_at,
                description=description,
            )
            if duplicate_id:
                return RejectDecision(
                    raw_event=raw_event,
                    reason="duplicate_strict",
                    details={
                        "duplicate_of": duplicate_id,
                        "window_hours": self.settings.duplicate_window_hours,
                        "coord_precision": self.settings.duplicate_coord_precision,
                    },
                )

        description_redacted = description if has_description else None
        canonical = CanonicalEvent(
            service_request_id=raw_event.service_request_id,
            title=raw_event.title,
            description=raw_event.description,
            description_redacted=description_redacted,
            requested_at=requested_at,
            status=status,
            lat=raw_event.lat,
            lon=raw_event.lon,
            address_string=raw_event.address_string,
            service_name=raw_event.service_name,
            category=category["category"],
            subcategory=category["subcategory"],
            subcategory2=category["subcategory2"],
            media_path=media_path,
            year=year,
            sequence_number=sequence,
            has_description=has_description,
            has_media=has_media,
            skip_llm=skip_llm,
            is_link_only=link_only,
            is_flagged_abuse=False,
        )

        return AcceptDecision(
            raw_event=raw_event,
            normalized=canonical,
            review_reason=review_reason,
            review_details=review_details,
        )

    def _check_duplicate(
        self,
        raw_event: RawEvent,
        requested_at: datetime,
        description: str,
    ) -> Optional[str]:
        key = self._build_duplicate_key(raw_event, description)
        window = timedelta(hours=self.settings.duplicate_window_hours)

        for entry in self._seen.get(key, []):
            if abs(requested_at - entry.requested_at) <= window:
                return entry.service_request_id

        if self.duplicate_checker:
            duplicate_id = self.duplicate_checker.find_duplicate(key, requested_at)
            if duplicate_id:
                return duplicate_id

        self._seen.setdefault(key, []).append(
            DuplicateEntry(
                service_request_id=raw_event.service_request_id,
                requested_at=requested_at,
            )
        )
        return None

    def _build_duplicate_key(self, raw_event: RawEvent, description: str) -> DuplicateKey:
        precision = self.settings.duplicate_coord_precision
        service_name = (
            raw_event.service_name if self.settings.duplicate_require_service_name else None
        )
        address_string = (
            raw_event.address_string if self.settings.duplicate_require_address else None
        )

        return DuplicateKey(
            description=normalize_for_dedupe(description),
            lat_round=round(raw_event.lat or 0.0, precision),
            lon_round=round(raw_event.lon or 0.0, precision),
            service_name=service_name,
            address_string=address_string,
        )


_DEFAULT_GATE: Optional[QualityGate] = None


def evaluate(raw_event: RawEvent) -> AcceptDecision | RejectDecision:
    """Convenience evaluate wrapper using default settings."""
    global _DEFAULT_GATE
    if _DEFAULT_GATE is None:
        _DEFAULT_GATE = QualityGate()
    return _DEFAULT_GATE.evaluate(raw_event)
