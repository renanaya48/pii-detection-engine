"""Core types and the public output contract.

The public contract is deliberately small: ``type``, ``start``, ``end`` per
finding plus a response-level status. Evidence and source are internal (used
for merging and profile decisions) and never leave the engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class EntityType(str, Enum):
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CREDIT_CARD = "CREDIT_CARD"


class ScanStatus(str, Enum):
    """``COMPLETE`` means every configured recognizer finished, not that the text is PII-free."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class Evidence(IntEnum):
    """How strongly a recognizer backs a span. Ordered: higher wins overlaps.

    Regex and model scores are not comparable, so we rank by kind of evidence
    instead of by a raw confidence number.
    """

    HEURISTIC = 0  # recovered by a heuristic that raises false-positive risk (e.g. phone prefix recovery)
    MODEL = 1  # statistical model output (NER)
    PATTERN = 2  # deterministic pattern match
    CHECKSUM = 3  # pattern match that also passed a checksum (e.g. Luhn)


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Per-request hints passed to recognizers. ``region`` is an upper-case ISO 3166 alpha-2 code."""

    region: str | None = None


@dataclass(frozen=True, slots=True)
class Span:
    """Internal finding. ``start``/``end`` are a half-open ``[start, end)`` range of code points."""

    type: EntityType
    start: int
    end: int
    evidence: Evidence

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("span must satisfy 0 <= start < end")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class ScanResult:
    status: ScanStatus
    spans: tuple[Span, ...] = ()

    def to_dict(self) -> dict:
        """Public representation: no evidence, no source, no matched text."""
        return {
            "status": self.status.value,
            "results": [{"type": s.type.value, "start": s.start, "end": s.end} for s in self.spans],
        }
