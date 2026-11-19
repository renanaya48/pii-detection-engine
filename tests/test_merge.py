from pii_engine.merge import resolve_overlaps
from pii_engine.types import EntityType as T
from pii_engine.types import Evidence as E
from pii_engine.types import Span


def test_checksum_card_beats_overlapping_phone():
    card = Span(T.CREDIT_CARD, 0, 19, E.CHECKSUM)
    phone = Span(T.PHONE, 3, 15, E.PATTERN)
    assert resolve_overlaps([phone, card]) == [card]


def test_pattern_beats_model_even_when_model_span_is_longer():
    email = Span(T.EMAIL, 10, 30, E.PATTERN)
    person = Span(T.PERSON, 5, 40, E.MODEL)
    assert resolve_overlaps([person, email]) == [email]


def test_same_evidence_prefers_longer_span_without_union():
    short = Span(T.PERSON, 0, 5, E.MODEL)
    long = Span(T.PERSON, 3, 12, E.MODEL)
    result = resolve_overlaps([short, long])
    assert result == [long]  # not a union (0, 12)


def test_non_overlapping_spans_are_all_kept_and_sorted():
    b = Span(T.EMAIL, 20, 30, E.PATTERN)
    a = Span(T.PERSON, 0, 5, E.MODEL)
    assert resolve_overlaps([b, a]) == [a, b]


def test_adjacent_spans_do_not_conflict():
    a = Span(T.PERSON, 0, 5, E.MODEL)
    b = Span(T.PERSON, 5, 9, E.MODEL)
    assert resolve_overlaps([a, b]) == [a, b]


def test_duplicates_collapse_and_result_is_deterministic():
    s = Span(T.EMAIL, 0, 8, E.PATTERN)
    assert resolve_overlaps([s, s, s]) == [s]
    x, y = Span(T.PHONE, 0, 8, E.PATTERN), Span(T.CREDIT_CARD, 0, 8, E.PATTERN)
    assert resolve_overlaps([x, y]) == resolve_overlaps([y, x])


def test_empty_input():
    assert resolve_overlaps([]) == []


def _reference(spans):
    """The original quadratic algorithm, kept as an oracle for the fast one."""
    from pii_engine.merge import _rank

    accepted = []
    for span in sorted(set(spans), key=_rank):
        if not any(span.overlaps(kept) for kept in accepted):
            accepted.append(span)
    return sorted(accepted, key=lambda s: (s.start, s.end))


def test_fast_merge_equals_the_reference_on_random_overlapping_inputs():
    import random

    rnd = random.Random(11)
    types, evidences = list(T), list(E)
    for _ in range(300):
        spans = []
        for _ in range(rnd.randint(0, 60)):
            start = rnd.randint(0, 120)
            spans.append(Span(rnd.choice(types), start, start + rnd.randint(1, 25), rnd.choice(evidences)))
        assert resolve_overlaps(spans) == _reference(spans)


def test_fast_merge_equals_the_reference_on_larger_inputs_with_mixed_lengths_and_evidence():
    import random

    rnd = random.Random(5)
    types, evidences = list(T), list(E)
    spans = []
    for _ in range(3_000):
        start = rnd.randint(0, 20_000)
        spans.append(Span(rnd.choice(types), start, start + rnd.randint(1, 40), rnd.choice(evidences)))
    assert resolve_overlaps(spans) == _reference(spans)


def test_random_order_inserts_stay_practical_at_the_largest_realistic_size():
    """Worst case for the sorted-list insert: disjoint spans accepted in random positional order
    (random evidence decides acceptance order). ~50k findings is the most a 100,000-char input can hold."""
    import random
    import time

    rnd = random.Random(3)
    starts = rnd.sample(range(0, 500_000, 10), 50_000)
    spans = [Span(T.EMAIL, s, s + 6, rnd.choice(list(E))) for s in starts]
    t0 = time.perf_counter()
    assert len(resolve_overlaps(spans)) == 50_000
    # ~0.4 s on an idle laptop. A quadratic algorithm with a large constant would take far longer.
    assert time.perf_counter() - t0 < 10


def test_many_valid_findings_resolve_in_near_linear_time():
    """Regression: 14k non-overlapping spans took 12.7 s with the quadratic version."""
    import time

    spans = [Span(T.EMAIL, i * 7, i * 7 + 6, E.PATTERN) for i in range(15_000)]
    started = time.perf_counter()
    assert len(resolve_overlaps(spans)) == 15_000
    # ~0.1 s on an idle machine; the quadratic version needed ~12 s, so 3 s separates them even when busy.
    assert time.perf_counter() - started < 3
