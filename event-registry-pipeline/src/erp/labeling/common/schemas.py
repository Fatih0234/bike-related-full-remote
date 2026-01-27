"""LLM output schemas and normalization helpers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Phase1Output(BaseModel):
    """Structured output for Phase 1 (bike-related)."""

    label: Literal["true", "false", "uncertain"]
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value


PHASE2_CATEGORIES: tuple[str, ...] = (
    "Sicherheit & Komfort (Geometrie/Führung)",
    "Müll / Scherben / Splitter (Sharp objects & debris)",
    "Oberflächenqualität / Schäden",
    "Wasser / Eis / Entwässerung",
    "Hindernisse & Blockaden (inkl. Parken & Baustelle)",
    "Vegetation & Sichtbehinderung",
    "Markierungen & Beschilderung",
    "Ampeln & Signale (inkl. bike-specific Licht)",
    "Other / Unklar",
)


class Phase2Output(BaseModel):
    """Structured output for Phase 2 (bike-issue category)."""

    category: str
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = ""
    confidence: float = 0.0

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if value not in PHASE2_CATEGORIES:
            raise ValueError("Invalid category (must match one of PHASE2_CATEGORIES exactly)")
        return value

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value


def bike_related_from_label(label: str) -> bool | None:
    """Map Phase 1 label string to a nullable boolean."""
    if label == "true":
        return True
    if label == "false":
        return False
    if label == "uncertain":
        return None
    raise ValueError(f"Unexpected label: {label!r}")


def truncate_evidence(items: list[str], max_items: int = 10, max_chars: int = 200) -> list[str]:
    """Truncate evidence list for DB storage and dashboard readability."""
    cleaned: list[str] = []
    for item in items[:max_items]:
        value = (item or "").strip()
        if not value:
            continue
        cleaned.append(value[:max_chars])
    return cleaned


def truncate_reasoning(text: str, max_chars: int = 500) -> str:
    """Truncate reasoning for DB storage."""
    return (text or "").strip()[:max_chars]

