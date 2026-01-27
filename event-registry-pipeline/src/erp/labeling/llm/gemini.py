"""Gemini REST client for structured JSON labeling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional, TypeVar

import httpx
import orjson
from pydantic import BaseModel, ValidationError

from erp.config import Settings


T = TypeVar("T", bound=BaseModel)


REPAIR_SUFFIX = (
    "\n\nIMPORTANT: Return ONLY a single JSON object. No markdown. No code fences. "
    "Do not add any extra keys. Ensure types and allowed values match the schema."
)


def _extract_text_from_response(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini response missing candidates")

    content = (candidates[0].get("content") or {})
    parts = content.get("parts") or []
    texts: list[str] = []
    for part in parts:
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    if not texts:
        raise ValueError("Gemini response missing text parts")
    return "\n".join(texts).strip()


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


def _extract_json_string(text: str) -> str:
    candidate = _strip_code_fences(text)
    try:
        orjson.loads(candidate)
        return candidate
    except Exception:
        pass

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        maybe = candidate[start : end + 1].strip()
        orjson.loads(maybe)
        return maybe

    raise ValueError("Could not extract valid JSON from model output")


@dataclass(frozen=True)
class GeminiResult:
    text: str
    latency_ms: int


class GeminiClient:
    """Minimal REST client for Gemini generateContent."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        if not self.settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY must be set for Gemini labeling")

    def _request(self, prompt: str) -> GeminiResult:
        url = (
            f"{self.settings.gemini_api_base_url}/models/"
            f"{self.settings.gemini_model_id}:generateContent"
        )
        params = {"key": self.settings.google_api_key}
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.settings.gemini_temperature,
                "maxOutputTokens": self.settings.gemini_max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        start = time.time()
        with httpx.Client(timeout=self.settings.open311_timeout_seconds) as client:
            response = client.post(url, params=params, json=body)
            response.raise_for_status()
            payload = response.json()

        latency_ms = int((time.time() - start) * 1000)
        text = _extract_text_from_response(payload)
        return GeminiResult(text=text, latency_ms=latency_ms)

    def generate_structured(self, prompt: str, schema: type[T]) -> tuple[Optional[T], int, int, str | None]:
        """Generate and validate structured JSON output.

        Returns (output, total_latency_ms, attempts, error_message).
        """
        total_latency = 0
        last_error: str | None = None
        attempts = max(1, self.settings.labeling_max_retries)

        for attempt in range(1, attempts + 1):
            suffix = "" if attempt == 1 else REPAIR_SUFFIX
            try:
                result = self._request(prompt + suffix)
                total_latency += result.latency_ms
                json_str = _extract_json_string(result.text)
                parsed = schema.model_validate_json(json_str)
                return parsed, total_latency, attempt, None
            except (httpx.HTTPError, ValidationError, ValueError) as exc:
                last_error = str(exc)
                if attempt < attempts:
                    time.sleep(self.settings.labeling_sleep_seconds)
                continue

        return None, total_latency, attempts, last_error

