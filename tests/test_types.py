import pytest

from pii_engine.types import EntityType, Evidence, ScanResult, ScanStatus, Span


def test_span_rejects_empty_or_negative_ranges():
    with pytest.raises(ValueError):
        Span(EntityType.EMAIL, 5, 5, Evidence.PATTERN)
    with pytest.raises(ValueError):
        Span(EntityType.EMAIL, -1, 3, Evidence.PATTERN)


def test_overlap_is_half_open():
    a = Span(EntityType.PERSON, 0, 5, Evidence.MODEL)
    adjacent = Span(EntityType.PERSON, 5, 8, Evidence.MODEL)
    inside = Span(EntityType.PERSON, 4, 8, Evidence.MODEL)
    assert not a.overlaps(adjacent)
    assert a.overlaps(inside)


def test_public_output_has_only_type_start_end_and_status():
    result = ScanResult(ScanStatus.PARTIAL, (Span(EntityType.EMAIL, 3, 10, Evidence.CHECKSUM),))
    assert result.to_dict() == {
        "status": "partial",
        "results": [{"type": "EMAIL", "start": 3, "end": 10}],
    }


def test_empty_result_is_valid():
    assert ScanResult(ScanStatus.COMPLETE).to_dict() == {"status": "complete", "results": []}
