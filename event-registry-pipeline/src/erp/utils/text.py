"""Text helpers."""

from __future__ import annotations

import re
from typing import Optional


def extract_media_path(media_url: Optional[str]) -> Optional[str]:
    """Extract relative media path from a full URL."""
    if not media_url:
        return None
    match = re.search(r"/files/(.+)$", media_url)
    return match.group(1) if match else None


def normalize_whitespace(text: str) -> str:
    """Collapse whitespace and trim."""
    return re.sub(r"\s+", " ", text).strip()


def strip_urls(text: str) -> str:
    """Remove URLs from text."""
    return re.sub(r"https?://\S+|www\.\S+", "", text)


def is_link_only(text: str, min_chars: int = 3) -> bool:
    """Return True if text is effectively only URLs or very short."""
    cleaned = normalize_whitespace(strip_urls(text))
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return len(cleaned) < min_chars


def normalize_for_dedupe(text: str) -> str:
    """Normalize text for strict duplicate checks."""
    return normalize_whitespace(strip_urls(text)).lower()
