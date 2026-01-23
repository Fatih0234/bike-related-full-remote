from erp.ingestion.quality_gate import evaluate
from erp.models import RawEvent


def test_quality_gate_sets_skip_llm_on_empty_description():
    raw = RawEvent(
        service_request_id="12-2026",
        title="Test",
        description="",
        lat=50.0,
        long=6.0,
        payload={},
    )

    decision = evaluate(raw)
    assert decision.reason == "accepted"
    assert decision.normalized is not None
    assert decision.normalized.skip_llm is True
