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
