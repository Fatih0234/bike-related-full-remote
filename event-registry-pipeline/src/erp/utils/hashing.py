"""Hashing helpers for prompt and input tracking."""

from __future__ import annotations

import hashlib


def hash_text(value: str) -> str:
    """Return a short SHA-256 hash for the provided text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
