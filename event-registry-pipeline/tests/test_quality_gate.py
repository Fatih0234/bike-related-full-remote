from erp.ingestion.quality_gate import QualityGate
from erp.models import RawEvent


def _base_event(**overrides) -> RawEvent:
    payload = {
        "service_request_id": "12-2026",
        "requested_datetime": "2026-01-15T23:34:39+01:00",
        "lat": 50.0,
        "long": 6.0,
        "service_name": "Wilder Müll",
        "title": "Test",
        "description": "Test description",
        "address_string": "50859 Köln, Teststraße 1",
        "status": "open",
    }
    payload.update(overrides)
    return RawEvent.model_validate({**payload, "payload": payload})


def test_quality_gate_sets_skip_llm_on_empty_description():
    gate = QualityGate()
    raw = _base_event(description="")
    decision = gate.evaluate(raw)
    assert decision.reason == "accepted"
    assert decision.normalized is not None
    assert decision.normalized.skip_llm is True


def test_quality_gate_rejects_missing_requested_at():
    gate = QualityGate()
    raw = _base_event(requested_datetime=None)
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_requested_at"


def test_quality_gate_rejects_invalid_coords():
    gate = QualityGate()
    raw = _base_event(lat=200.0)
    decision = gate.evaluate(raw)
    assert decision.reason == "invalid_coords"


def test_quality_gate_flags_link_only():
    gate = QualityGate()
    raw = _base_event(description="https://example.com")
    decision = gate.evaluate(raw)
    assert decision.reason == "accepted"
    assert decision.normalized is not None
    assert decision.normalized.is_link_only is True


def test_quality_gate_rejects_invalid_status():
    gate = QualityGate()
    raw = _base_event(status="pending")
    decision = gate.evaluate(raw)
    assert decision.reason == "invalid_status"


def test_quality_gate_rejects_missing_address():
    gate = QualityGate()
    raw = _base_event(address_string="")
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_address_string"


def test_quality_gate_rejects_strict_duplicate():
    gate = QualityGate()
    first = _base_event(service_request_id="10-2026")
    second = _base_event(service_request_id="11-2026")
    first_decision = gate.evaluate(first)
    assert first_decision.reason == "accepted"

    second_decision = gate.evaluate(second)
    assert second_decision.reason == "duplicate_strict"


def test_quality_gate_accepts_unmapped_service_name():
    gate = QualityGate()
    raw = _base_event(service_name="Stadtbild")
    decision = gate.evaluate(raw)
    assert decision.reason == "accepted"
    assert decision.review_reason == "unmapped_service_name"
    assert decision.normalized is not None
    assert decision.normalized.category == "Unmapped"


def test_quality_gate_rejects_spam_text():
    gate = QualityGate()
    raw = _base_event(description="test")
    decision = gate.evaluate(raw)
    assert decision.reason == "spam_text"


def test_quality_gate_rejects_missing_service_request_id():
    gate = QualityGate()
    raw = _base_event(service_request_id=None)
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_service_request_id"


def test_quality_gate_rejects_missing_service_name():
    gate = QualityGate()
    raw = _base_event(service_name="")
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_service_name"


def test_quality_gate_rejects_missing_title():
    gate = QualityGate()
    raw = _base_event(title="")
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_title"


def test_quality_gate_rejects_missing_coords():
    gate = QualityGate()
    raw = _base_event(lat=None, long=None)
    decision = gate.evaluate(raw)
    assert decision.reason == "missing_coords"


def test_quality_gate_sets_has_media_flag():
    gate = QualityGate()
    payload = {
        "service_request_id": "12-2026",
        "requested_datetime": "2026-01-15T23:34:39+01:00",
        "lat": 50.0,
        "long": 6.0,
        "service_name": "Wilder Müll",
        "title": "Test",
        "description": "Test description",
        "address_string": "50859 Köln, Teststraße 1",
        "status": "open",
        "media_url": "https://sags-uns.stadt-koeln.de/system/files/2026-01/test.jpg",
        "payload": {},
    }
    raw = RawEvent.model_validate(payload)
    decision = gate.evaluate(raw)
    assert decision.reason == "accepted"
    assert decision.normalized is not None
    assert decision.normalized.has_media is True
    assert decision.normalized.media_path == "2026-01/test.jpg"
