from erp.ingestion.incremental import compute_gap_ids, max_sequence_for_year


def test_compute_gap_ids_builds_expected_range():
    ids = compute_gap_ids(last_sequence=34, max_sequence=100, year=2026)
    assert ids[0] == "35-2026"
    assert ids[-1] == "100-2026"
    assert len(ids) == 66


def test_compute_gap_ids_handles_no_new_ids():
    assert compute_gap_ids(last_sequence=100, max_sequence=100, year=2026) == []


def test_max_sequence_for_year():
    ids = ["1-2025", "20-2025", "5-2026", "17-2025"]
    assert max_sequence_for_year(ids, 2025) == 20
    assert max_sequence_for_year(ids, 2026) == 5
