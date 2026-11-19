"""Split long text into overlapping segments and map findings back to original offsets.

Why this exists: NER memory and latency grow with input length. Measured unsegmented (English
model, one core): peak process memory 133 MB at 5k chars, 167 MB at 20k, 236 MB at 50k, 347 MB at
100k, so segmentation is required to stay inside the 150 MB budget, not just for convenience.

Boundary rules (they are what makes entities at segment edges safe):
* A segment ends at the last whitespace in its second half (hard cut only if there is none).
* The next segment starts at the last whitespace strictly before ``end - overlap``, so consecutive
  segments share AT LEAST ``overlap`` characters.
* A span that touches an interior edge of its segment may be cut by that edge, so it is dropped
  there. The guaranteed overlap means a span SHORTER than ``overlap`` characters lies whole, and
  not touching an edge, in the neighbouring segment.

What this does and does not guarantee (coverage limits, stated plainly):
* Spans of ``overlap`` characters or more can be lost at an edge. A model may also return an
  unusually long span for an ordinary name; that span is subject to this limit.
* The guarantee covers the mechanism, assuming a recognizer returns the same span for an entity
  wherever it sits. A statistical model sees different context in each segment, so that is an
  empirical property, not a proof: tests/test_integration_real_model.py sweeps a name across the
  edges with the real model, and an offline sweep of 258 positions found it whole exactly once.
* Different NER output near an edge is possible for other names, texts and models.
Offsets are Python string indices, i.e. Unicode code points.
"""
from __future__ import annotations

from dataclasses import dataclass

from .types import Span


@dataclass(frozen=True, slots=True)
class Segment:
    start: int  # offset of this segment in the original text
    text: str
    first: bool
    last: bool

    def keep(self, span: Span) -> bool:
        """False if the span touches an interior edge and may therefore be cut off."""
        if span.start == 0 and not self.first:
            return False
        if span.end == len(self.text) and not self.last:
            return False
        return True

    def to_global(self, span: Span) -> Span:
        return Span(span.type, span.start + self.start, span.end + self.start, span.evidence)


def segment(text: str, size: int, overlap: int) -> list[Segment]:
    if not (0 < 2 * overlap < size):
        raise ValueError("need 0 < 2 * overlap < size")
    n = len(text)
    if n <= size:
        return [Segment(0, text, True, True)]

    segments: list[Segment] = []
    start = 0
    while True:
        end = _break_before(text, start, min(start + size, n), size)
        segments.append(Segment(start, text[start:end], first=not segments, last=end == n))
        if end == n:
            return segments
        start = _next_start(text, start, end - overlap)


def _break_before(text: str, start: int, end: int, size: int) -> int:
    """End of a segment: the last whitespace in the second half of the window, else a hard cut."""
    if end == len(text):
        return end
    for i in range(end - 1, start + size // 2 - 1, -1):
        if text[i].isspace():
            return i + 1
    return end


def _next_start(text: str, prev_start: int, target: int) -> int:
    """Start after the last whitespace strictly before ``target``; never at or before the previous start."""
    for i in range(target - 1, prev_start, -1):
        if text[i].isspace():
            return i + 1
    return target
