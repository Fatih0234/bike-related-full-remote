import pytest

from erp.labeling.common.schemas import (
    PHASE2_CATEGORIES,
    Phase1Output,
    Phase2Output,
    bike_related_from_label,
    truncate_evidence,
    truncate_reasoning,
)


def test_bike_related_mapping():
    assert bike_related_from_label("true") is True
    assert bike_related_from_label("false") is False
    assert bike_related_from_label("uncertain") is None
    with pytest.raises(ValueError):
        bike_related_from_label("maybe")


def test_truncate_evidence():
    evidence = ["   abcdefghijkl  ", "  ", " xyz "]
    truncated = truncate_evidence(evidence, max_items=3, max_chars=5)
    assert truncated == ["abcde", "xyz"]


def test_truncate_reasoning():
    assert truncate_reasoning("  hello  ", max_chars=10) == "hello"


def test_phase1_schema_clamps_confidence():
    out = Phase1Output(label="true", confidence=2.0, evidence=["x"], reasoning="r")
    assert out.confidence == 1.0


def test_phase2_schema_validates_category():
    ok = Phase2Output(category=PHASE2_CATEGORIES[0], confidence=0.5, evidence=["x"], reasoning="r")
    assert ok.category == PHASE2_CATEGORIES[0]
    with pytest.raises(ValueError):
        Phase2Output(category="Not a category", confidence=0.5, evidence=["x"], reasoning="r")
