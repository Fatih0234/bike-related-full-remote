"""Core data models for ingestion and labeling."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class RawEvent(BaseModel):
    """Raw Open311 event with original payload."""

    service_request_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    requested_datetime: Optional[str] = None
    status: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = Field(default=None, alias="long")
    address_string: Optional[str] = None
    service_name: Optional[str] = None
    media_url: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CanonicalEvent(BaseModel):
    """Normalized event ready for the canonical table."""

    service_request_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    requested_at: Optional[str] = None
    status: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    address_string: Optional[str] = None
    service_name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    subcategory2: Optional[str] = None
    media_path: Optional[str] = None
    year: Optional[int] = None
    sequence_number: Optional[int] = None
    has_description: bool = False
    skip_llm: bool = False


class AcceptDecision(BaseModel):
    """Quality gate acceptance."""

    raw_event: RawEvent
    normalized: Optional[CanonicalEvent] = None
    reason: str = "accepted"


class RejectDecision(BaseModel):
    """Quality gate rejection."""

    raw_event: RawEvent
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
