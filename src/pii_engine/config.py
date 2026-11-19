"""Engine limits and detection profiles."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .types import EntityType, Evidence, Span


@dataclass(frozen=True, slots=True)
class Limits:
    """Explicit design caps, not benchmark facts."""

    max_chars: int = 100_000  # longer input is rejected (status FAILED), never silently truncated
    regex_timeout_s: float = 0.05  # per pattern, per 10,000 chars (scaled up for longer text); a timeout keeps the findings so far and marks the scan PARTIAL
    segment_chars: int = 4_000  # NER segment size; keeps peak memory near the 5k-char point (see segmenter)
    segment_overlap: int = 200  # entities shorter than this are never lost at a segment edge


@dataclass(frozen=True, slots=True)
class Profile:
    """Decides which findings surface. It never decides what happens to them (that is the caller's job).

    Rules are explicit and evidence-based rather than numeric thresholds, because regex and model
    scores are not comparable and the NER model exposes no probability.

    * ``min_evidence``: weakest evidence accepted per entity type.
    * ``person_min_words``: an optional rule (1 = off). Balanced used to require two words on the
      guess that one-word hits from a small model are mostly non-names. Measured on real informal text
      (WNUT-17 dev, 192 mentions) that was wrong: it cut PERSON recall from 35.4% to 7.3% and did
      NOT improve precision (38.9% vs 51.9%), because most names in such text are one token. No built-in
      profile uses it now; it stays available for callers working on formal text where it may pay off.
    """

    name: str
    min_evidence: Mapping[EntityType, Evidence]
    person_min_words: int

    def accepts(self, span: Span, text: str) -> bool:
        if span.evidence < self.min_evidence[span.type]:
            return False
        if span.type is EntityType.PERSON and len(text[span.start : span.end].split()) < self.person_min_words:
            return False
        return True


STRICT = Profile(
    "strict",
    {
        EntityType.PERSON: Evidence.MODEL,
        EntityType.EMAIL: Evidence.PATTERN,
        EntityType.PHONE: Evidence.HEURISTIC,  # also numbers recovered from digit-suffixed chains
        EntityType.CREDIT_CARD: Evidence.HEURISTIC,  # also unknown-brand and oddly grouped Luhn-valid numbers
    },
    person_min_words=1,
)

BALANCED = Profile(
    "balanced",
    {
        EntityType.PERSON: Evidence.MODEL,
        EntityType.EMAIL: Evidence.PATTERN,
        EntityType.PHONE: Evidence.PATTERN,
        EntityType.CREDIT_CARD: Evidence.CHECKSUM,  # known brand + Luhn only
    },
    person_min_words=1,
)

PROFILES: Mapping[str, Profile] = {p.name: p for p in (STRICT, BALANCED)}
DEFAULT_PROFILE = "balanced"
