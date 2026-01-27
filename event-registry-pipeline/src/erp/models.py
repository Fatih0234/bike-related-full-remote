"""Core data models for ingestion and labeling."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class RawEvent(BaseModel):
    """Raw Open311 event with original payload."""

    model_config = ConfigDict(extra="ignore")

    service_request_id: Optional[str] = None
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

    model_config = ConfigDict(extra="ignore")

    service_request_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    description_redacted: Optional[str] = None
    requested_at: Optional[datetime] = None
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
    has_media: bool = False
    skip_llm: bool = False
    is_link_only: bool = False
    is_flagged_abuse: bool = False


class AcceptDecision(BaseModel):
    """Quality gate acceptance."""

    raw_event: RawEvent
    normalized: Optional[CanonicalEvent] = None
    reason: str = "accepted"
    review_reason: Optional[str] = None
    review_details: dict[str, Any] = Field(default_factory=dict)


class RejectDecision(BaseModel):
    """Quality gate rejection."""

    raw_event: RawEvent
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
