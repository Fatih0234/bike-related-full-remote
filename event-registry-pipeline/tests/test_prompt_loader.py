from pathlib import Path

import pytest

from erp.labeling.common.prompt_loader import load_prompt, prompt_path


def test_prompt_path_maps_versions():
    p1 = prompt_path(phase=1, prompt_version="p1_v006")
    assert p1.as_posix().endswith("prompts/phase1/v006.md")
    p2 = prompt_path(phase=2, prompt_version="p2_v001")
    assert p2.as_posix().endswith("prompts/phase2/v001.md")


def test_prompt_path_rejects_bad_prefix():
    with pytest.raises(ValueError):
        prompt_path(phase=1, prompt_version="v006")


def test_load_prompt_reads_existing_file():
    prompt = load_prompt(phase=1, prompt_version="p1_v006")
    assert isinstance(prompt, str)
    assert len(prompt) > 10
    # Ensure the file is part of the repo (basic sanity check)
    assert Path("prompts/phase1/v006.md").exists()

