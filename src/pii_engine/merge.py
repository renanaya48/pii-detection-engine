"""Overlap resolution.

Rules (documented because they are a design decision, not an accident):

1. Overlapping spans compete; exactly one survives per overlap group.
2. Winner order: stronger evidence (CHECKSUM > PATTERN > MODEL > HEURISTIC), then the
   longer span, then the earlier start, then a fixed type order.
3. Losers are dropped whole. We never trim a span or union two spans, so the
   engine cannot report a range that no recognizer actually produced.

Example: a Luhn-valid CREDIT_CARD beats an overlapping PHONE; an EMAIL beats an
overlapping NER PERSON (the model tagging "john.smith" inside an address).

Cost: sorting is O(n log n) and each overlap check is a binary search, so comparisons are
O(n log n). Inserting into the sorted Python list shifts elements, so the total work is still
quadratic in the worst case, with a very small constant (one memmove per insert). That worst case needs
accepted spans to arrive in random positional order, which happens when evidence and length vary.
Measured with random evidence and positions: 14,000 spans 56 ms, 50,000 spans 434 ms, 100,000 spans
1.7 s. A 100,000-character input holds at most ~50,000 findings, so this is acceptable at the input
cap. The first version compared every span with every accepted span: 12.7 s for 14,285 valid emails.
"""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable

from .types import EntityType, Span

_TYPE_ORDER = {t: i for i, t in enumerate(EntityType)}


def _rank(span: Span) -> tuple:
    return (-span.evidence, -span.length, span.start, _TYPE_ORDER[span.type])


def resolve_overlaps(spans: Iterable[Span]) -> list[Span]:
    """Return non-overlapping spans sorted by position."""
    starts: list[int] = []  # start offsets of accepted spans, ascending (they are disjoint)
    accepted: list[Span] = []  # same order as ``starts``
    for span in sorted(set(spans), key=_rank):
        i = bisect_right(starts, span.start)
        before = accepted[i - 1] if i > 0 else None  # last accepted span starting at or before ours
        after = accepted[i] if i < len(accepted) else None  # first accepted span starting after ours
        if (before and before.end > span.start) or (after and after.start < span.end):
            continue
        starts.insert(i, span.start)
        accepted.insert(i, span)
    return accepted
