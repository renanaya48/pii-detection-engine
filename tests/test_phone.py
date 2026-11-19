import time

import pytest

from pii_engine.recognizers import IncompleteScan
from pii_engine.recognizers.phone import PhoneRecognizer, _budget_exhausted
from pii_engine.types import Evidence, ScanContext

rec = PhoneRecognizer()


def found(text, region=None):
    return [text[s.start : s.end] for s in rec.analyze(text, ScanContext(region))]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("call +1 415-555-2671 today", ["+1 415-555-2671"]),
        ("tel: +44 20 7946 0958.", ["+44 20 7946 0958"]),
        ("whatsapp +34 612 345 678", ["+34 612 345 678"]),
        ("appelez +33 1 70 18 99 00", ["+33 1 70 18 99 00"]),
    ],
)
def test_international_numbers_match_without_region(text, expected):
    assert found(text) == expected


def test_local_format_needs_a_region_hint():
    text = "call (415) 555-2671 tomorrow"
    assert found(text) == []
    assert found(text, "US") == ["(415) 555-2671"]


def test_region_is_not_inferred_from_language():
    # Spanish text, but without a region a bare local number is not guessed.
    assert found("llámame al 612 345 678 mañana") == []
    assert found("llámame al 612 345 678 mañana", "ES") == ["612 345 678"]


@pytest.mark.parametrize(
    "text",
    ["2024-05-17", "order 1234567", "version 3.10.12", "amount 1,250.00", "+1 000 000 0000", "ID 123456789012345678"],
)
def test_rejects_look_alikes(text):
    assert found(text) == []
    assert found(text, "US") == []


def test_unsupported_region_raises_so_engine_can_mark_partial():
    with pytest.raises(ValueError):
        rec.analyze("x", ScanContext("ZZ"))


def test_offsets_are_code_points():
    text = "😀 +1 415-555-2671"
    span = rec.analyze(text, ScanContext())[0]
    assert text[span.start : span.end] == "+1 415-555-2671"


@pytest.mark.parametrize("junk", ["+1 ", "1 2 ", "12 ", "1-", "(1) "])
@pytest.mark.parametrize("repeats", [2_000, 20_000])
def test_junk_padding_cannot_hide_a_real_number(junk, repeats):
    text = junk * repeats + " call +44 20 7946 0958"
    assert any(text[s.start : s.end] == "+44 20 7946 0958" for s in rec.analyze(text, ScanContext()))


def test_number_straddling_a_window_boundary_is_found_whole():
    number = "+44 20 7946 0958"
    for pad in range(960, 1000, 3):  # sweep the number across the first window edge
        text = "x" * pad + number + " end"
        spans = [text[s.start : s.end] for s in rec.analyze(text, ScanContext())]
        assert number in spans, pad


def _tiny_budget(monkeypatch, tries=5):
    monkeypatch.setattr("pii_engine.recognizers.phone._MAX_TRIES", tries)


def test_exhausted_budget_is_reported_and_keeps_spans_found_so_far(monkeypatch):
    _tiny_budget(monkeypatch)
    text = "call +44 20 7946 0958 now. " + "1 2 " * 200
    with pytest.raises(IncompleteScan) as info:
        rec.analyze(text, ScanContext())
    assert any(text[s.start : s.end] == "+44 20 7946 0958" for s in info.value.spans)


@pytest.mark.parametrize("suffix", [" 12", " 1 2 1 2 1 2", " 123456", " 2024-05-17", " ext 55"])
def test_trailing_digits_cannot_hide_a_valid_international_number(suffix):
    number = "+44 20 7946 0958"
    text = f"my number is {number}{suffix} thanks"
    start = text.index(number)
    # Covered, never missed. For " ext 55" the matcher accepts the number together with its extension
    # (a larger span), so the exact number text is not always a span of its own.
    assert any(s.start <= start and s.end >= start + len(number) for s in rec.analyze(text, ScanContext()))


def test_trailing_digit_recovery_reports_only_the_number():
    text = "+44 20 7946 0958 12"
    spans = [text[s.start : s.end] for s in rec.analyze(text, ScanContext())]
    assert spans == ["+44 20 7946 0958"]


def test_matcher_valid_numbers_are_pattern_and_recovered_ones_are_heuristic():
    clean = rec.analyze("call +44 20 7946 0958 now", ScanContext())
    assert [s.evidence for s in clean] == [Evidence.PATTERN]
    recovered = rec.analyze("call +44 20 7946 0958 12 now", ScanContext())
    assert [s.evidence for s in recovered] == [Evidence.HEURISTIC]


@pytest.mark.parametrize(
    "text",
    [
        "+100 points awarded",
        "scored +1.5% vs last year",
        "C++ 11 14 17 20 standard",
        "temperature +25 12 30 degrees",
        "balance +1 000 000 000 EUR",
        "+49 percent growth in 2024 2025",
        "add +1 2 3 4 5 6 7 8",
    ],
)
def test_realistic_non_phone_plus_contexts_produce_no_findings(text):
    assert rec.analyze(text, ScanContext()) == []


def test_recovery_never_upgrades_to_pattern_evidence_on_random_chains():
    import random

    rnd = random.Random(7)
    for _ in range(500):
        groups = ["".join(rnd.choice("0123456789") for _ in range(rnd.randint(1, 4))) for _ in range(rnd.randint(4, 9))]
        text = "+" + rnd.choice("123456789") + " " + " ".join(groups)
        for span in rec.analyze(text, ScanContext()):
            direct = phonenumbers_matches(text)
            assert span.evidence is Evidence.PATTERN or (span.start, span.end) not in direct


def phonenumbers_matches(text):
    import phonenumbers

    return {(m.start, m.end) for m in phonenumbers.PhoneNumberMatcher(text, None, leniency=phonenumbers.Leniency.VALID)}


def test_parse_budget_exhaustion_is_reported(monkeypatch):
    monkeypatch.setattr("pii_engine.recognizers.phone._MAX_PARSES", 10)
    with pytest.raises(IncompleteScan):
        rec.analyze("+1 2 3 4 5 6 7 8 9 " * 50, ScanContext())


def test_adversarial_plus_chains_do_bounded_work_and_are_reported_incomplete(monkeypatch):
    """Asserts the WORK bound (parse count), which is deterministic; wall time depends on the machine.

    Measured on an idle laptop: ~0.5-0.7 s for 100k hostile chars (was ~1.8 s before the parse budget);
    about twice that when the machine is busy. The wall-time cap below is only a hang guard.
    """
    import phonenumbers

    from pii_engine.recognizers import phone

    parses = []
    real_parse = phonenumbers.parse
    monkeypatch.setattr(phonenumbers, "parse", lambda *a, **k: parses.append(1) or real_parse(*a, **k))
    for payload in ["+1 2 3 4 5 6 7 8 9 " * 5_000, "+123456 " * 14_000]:
        parses.clear()
        t0 = time.perf_counter()
        with pytest.raises(IncompleteScan):
            rec.analyze(payload[:100_000], ScanContext())
        assert len(parses) <= phone._MAX_PARSES  # the per-call budget held
        assert time.perf_counter() - t0 < 10  # hang guard only


def test_a_document_full_of_valid_numbers_is_complete_not_partial():
    """Regression: recovery re-parsed every accepted number and exhausted its budget (5,882 numbers -> PARTIAL)."""
    text = "+44 20 7946 0958 " * 5_000
    spans = rec.analyze(text, ScanContext())  # must not raise IncompleteScan
    assert len(spans) == 5_000 and {s.evidence for s in spans} == {Evidence.PATTERN}


def test_recovery_still_runs_for_rejected_candidates_in_a_document_of_valid_numbers():
    text = "+44 20 7946 0958 " * 50 + "+44 20 7946 0958 12 " + "+44 20 7946 0958 " * 50
    heuristic = [s for s in rec.analyze(text, ScanContext()) if s.evidence is Evidence.HEURISTIC]
    assert len(heuristic) == 1


def test_too_many_plus_candidates_is_reported_not_skipped():
    text = "+123456 " * 140  # more candidates than the per-window cap
    with pytest.raises(IncompleteScan):
        rec.analyze(text, ScanContext())


def test_unexhausted_budget_is_not_reported_as_incomplete(monkeypatch):
    _tiny_budget(monkeypatch, tries=1_000)
    assert rec.analyze("call +44 20 7946 0958 now", ScanContext())  # no exception


def test_budget_signal_matches_the_library_attribute():
    """Pins the private-attribute assumption behind exhaustion detection."""
    import phonenumbers

    junk = "1 2 " * 100
    spent = phonenumbers.PhoneNumberMatcher(junk, None, max_tries=5)
    list(spent)
    assert _budget_exhausted(spent) is True
    fresh = phonenumbers.PhoneNumberMatcher("call +44 20 7946 0958", None, max_tries=100)
    list(fresh)
    assert _budget_exhausted(fresh) is False


def test_missing_library_attribute_fails_safe():
    class _NoAttr:
        pass

    with pytest.raises(RuntimeError):
        _budget_exhausted(_NoAttr())  # type: ignore[arg-type]


def test_adversarial_inputs_are_bounded():
    payloads = ["1" * 100_000, "+1 " * 30_000, "(" * 100_000, "1-" * 50_000, "+" + "9 " * 40_000]
    for payload in payloads:
        for region in (None, "US"):
            t0 = time.perf_counter()
            rec.analyze(payload, ScanContext(region))
            assert time.perf_counter() - t0 < 3.0, (payload[:6], region)
