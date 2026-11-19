"""Scan orchestration: segment, run recognizers, isolate failures, filter by profile, merge, return the public contract."""
from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .config import DEFAULT_PROFILE, PROFILES, Limits, Profile
from .langid import Language, detect
from .merge import resolve_overlaps
from .metrics import Metrics
from .recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    IncompleteScan,
    PhoneRecognizer,
    Recognizer,
    SpacyPersonRecognizer,
    load_model,
)
from .segmenter import Segment, segment
from .types import ScanContext, ScanResult, ScanStatus, Span

_REGION = re.compile(r"[A-Za-z]{2}")


@dataclass
class _Outcome:
    """What one recognizer did across its segments."""

    spans: list[Span] = field(default_factory=list)
    ran: int = 0  # segments actually analysed
    failed: int = 0  # segments whose analysis raised
    incomplete: bool = False  # a recognizer stopped early (budget, or some segments failed)
    not_covered: bool = False  # a segment was skipped or only partly understood (language)


class Engine:
    def __init__(
        self,
        recognizers: Sequence[Recognizer],
        limits: Limits = Limits(),
        metrics: Metrics | None = None,
        profiles: Mapping[str, Profile] = PROFILES,
    ) -> None:
        self._recognizers = tuple(recognizers)
        self._limits = limits
        self.metrics = metrics or Metrics()
        self._profiles = profiles  # injectable so variants (e.g. for evaluation) need no module-level patching

    @property
    def max_chars(self) -> int:
        """Largest accepted input. Callers that read input must read with THIS limit, not their own copy."""
        return self._limits.max_chars

    def scan(self, text: str, *, region: str | None = None, profile: str = DEFAULT_PROFILE) -> ScanResult:
        """Never raises on bad input: invalid or oversized input yields FAILED, not an exception.

        ``region``: optional ISO 3166 alpha-2 code (e.g. "US"); enables local phone formats.
        ``profile``: "strict" or "balanced"; controls which findings surface.
        """
        started = time.perf_counter()
        result = self._scan(text, region, profile)
        self.metrics.record_scan(
            (time.perf_counter() - started) * 1000,
            result.status.value,
            [s.type.value for s in result.spans],
        )
        return result

    def _scan(self, text: str, region: str | None, profile: str) -> ScanResult:
        if not isinstance(text, str) or len(text) > self._limits.max_chars:
            return ScanResult(ScanStatus.FAILED)
        if region is not None and not (isinstance(region, str) and _REGION.fullmatch(region)):
            return ScanResult(ScanStatus.FAILED)
        if not isinstance(profile, str) or profile not in self._profiles:
            return ScanResult(ScanStatus.FAILED)
        selected = self._profiles[profile]
        ctx = ScanContext(region.upper() if region else None)

        spans: list[Span] = []
        attempted = failed = 0
        partial = False
        whole = [Segment(0, text, True, True)]
        segments: list[Segment] | None = None  # computed once, only if a recognizer needs it
        for recognizer in self._recognizers:
            if getattr(recognizer, "segmented", False):
                segments = segments or segment(text, self._limits.segment_chars, self._limits.segment_overlap)
                outcome = self._run(recognizer, segments, ctx)
            else:
                outcome = self._run(recognizer, whole, ctx)

            spans.extend(outcome.spans)
            attempted += outcome.ran > 0
            if outcome.ran and outcome.failed == outcome.ran:
                failed += 1  # every segment failed: the recognizer produced nothing
            partial |= bool(outcome.failed or outcome.incomplete or outcome.not_covered)

        if attempted and failed == attempted:
            return ScanResult(ScanStatus.FAILED)
        status = ScanStatus.PARTIAL if partial else ScanStatus.COMPLETE

        # Filter BEFORE resolving overlaps: a span the profile rejects must not win an overlap
        # and thereby suppress a span that would have been accepted.
        accepted = [s for s in spans if selected.accepts(s, text)]
        return ScanResult(status, tuple(resolve_overlaps(accepted)))

    def _run(self, recognizer: Recognizer, segments: Sequence[Segment], ctx: ScanContext) -> _Outcome:
        out = _Outcome()
        gated = getattr(recognizer, "requires_english", False)
        for seg in segments:
            if gated:
                language = detect(seg.text)
                if language is Language.NO_TEXT:
                    continue  # no letters: nothing for this recognizer to find, and nothing uncovered
                if language is Language.OTHER:
                    out.not_covered = True
                    self.metrics.record_skip(recognizer.name, "language")
                    continue
                if language in (Language.MIXED, Language.UNCERTAIN):
                    out.not_covered = True  # runs best-effort; running does not prove the text is English
            out.ran += 1
            try:
                found = recognizer.analyze(seg.text, ctx)
            except IncompleteScan as exc:  # keep what was found, but the scan can't claim to be complete
                found = exc.spans
                out.incomplete = True
                self.metrics.record_error(recognizer.name, "IncompleteScan")
            except Exception as exc:  # isolate one recognizer's failure from the rest
                out.failed += 1
                self.metrics.record_error(recognizer.name, type(exc).__name__)
                continue
            out.spans.extend(seg.to_global(s) for s in found if seg.keep(s))
        return out


def default_engine(limits: Limits = Limits()) -> Engine:
    """English NER plus language-independent pattern recognizers."""
    return Engine(
        [
            EmailRecognizer(limits.regex_timeout_s),
            CreditCardRecognizer(limits.regex_timeout_s),
            PhoneRecognizer(),
            SpacyPersonRecognizer(load_model("en")),
        ],
        limits,
    )
