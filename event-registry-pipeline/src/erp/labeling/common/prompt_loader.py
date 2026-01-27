"""Prompt loading utilities."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def prompt_path(phase: int, prompt_version: str) -> Path:
    """Resolve a prompt file path from a prompt_version like 'p1_v006'."""
    if phase == 1:
        prefix = "p1_"
        folder = "phase1"
    elif phase == 2:
        prefix = "p2_"
        folder = "phase2"
    else:
        raise ValueError("phase must be 1 or 2")

    if not prompt_version.startswith(prefix):
        raise ValueError(f"prompt_version must start with {prefix!r}")

    file_stub = prompt_version.removeprefix(prefix)
    return PROJECT_ROOT / "prompts" / folder / f"{file_stub}.md"


def load_prompt(phase: int, prompt_version: str) -> str:
    """Load a prompt file as UTF-8 text."""
    path = prompt_path(phase=phase, prompt_version=prompt_version)
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()

