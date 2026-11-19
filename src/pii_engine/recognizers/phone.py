"""Phone numbers via the ``phonenumbers`` library (a port of libphonenumber).

Default (no region): only numbers in international format (leading ``+``) match. A local
format is considered only when the caller passes ``region``. This avoids guessing a country
from the text's language, which would create false positives. Leniency VALID requires the
number to be valid for its country, not merely digit-shaped.

Evasion guards (each one measured, see tests):
* Junk digits before a number can use up the matcher's per-call try budget, so the text is scanned
  in fixed windows with a fresh budget each. That makes exhaustion unlikely, not impossible; the real
  guarantee is reporting: if any budget runs out, the recognizer raises IncompleteScan (with the
  spans found so far) and the engine returns PARTIAL.
* Digits after a number make the matcher reject it ("+44 20 7946 0958 12"). We recover the longest
  valid prefix of '+' candidates. That is a heuristic: on random '+' digit chains it adds ~4x the
  false hits of the matcher, so recovered spans carry Evidence.HEURISTIC and only the strict profile
  accepts them. Its work is bounded by a per-window candidate cap and a per-scan parse budget; both
  report IncompleteScan when hit.
"""
from __future__ import annotations

import re

import phonenumbers

from ..types import EntityType, Evidence, ScanContext, Span
from .base import IncompleteScan

# International candidates (leading '+'): bounded length, linear to scan.
_INTL_CANDIDATE = re.compile(r"\+\d[\d ().\-]{5,29}")
_DIGIT_RUN = re.compile(r"\d+")
_MAX_CANDIDATES = 100  # per window
_MAX_PARSES = 1_500  # per analyze() call across all windows; ~21 us each, so ~30 ms worst case
_MAX_TRIES = 2_000  # matcher candidate budget per window
_WINDOW = 1_000  # chars; at ~1 candidate per 2 chars this should stay well under _MAX_TRIES
_OVERLAP = 100  # longer than any phone number, so a number cut by one window is whole in the next


class PhoneRecognizer:
    name = "phone"

    def analyze(self, text: str, ctx: ScanContext = ScanContext()) -> list[Span]:
        region = ctx.region
        if region is not None and region not in phonenumbers.SUPPORTED_REGIONS:
            raise ValueError("unsupported region")

        found: dict[tuple[int, int], Evidence] = {}
        incomplete = False
        parses_left = _MAX_PARSES
        step = _WINDOW - _OVERLAP
        for offset in range(0, max(len(text), 1), step):
            window = text[offset : offset + _WINDOW]
            matcher = phonenumbers.PhoneNumberMatcher(
                window, region, leniency=phonenumbers.Leniency.VALID, max_tries=_MAX_TRIES
            )
            accepted_starts: set[int] = set()
            for m in matcher:
                _record(found, (offset + m.start, offset + m.end), Evidence.PATTERN)
                accepted_starts.add(m.start)
            incomplete |= _budget_exhausted(matcher)

            recovered, parses_left, capped = _intl_prefix_matches(window, parses_left, accepted_starts)
            for s, e in recovered:
                _record(found, (offset + s, offset + e), Evidence.HEURISTIC)
            incomplete |= capped

            if offset + _WINDOW >= len(text):
                break
        # A window edge can yield a shorter valid prefix of a number that the next window sees whole;
        # both spans are returned and merge resolves them (same evidence -> longer span wins).
        spans = [Span(EntityType.PHONE, s, e, ev) for (s, e), ev in sorted(found.items())]
        if incomplete:
            raise IncompleteScan(spans)
        return spans


def _record(found: dict[tuple[int, int], Evidence], span: tuple[int, int], evidence: Evidence) -> None:
    """Keep the strongest evidence if the same range is seen twice (e.g. in overlapping windows)."""
    found[span] = max(found.get(span, evidence), evidence)


def _intl_prefix_matches(
    window: str, parses_left: int, accepted_starts: set[int]
) -> tuple[list[tuple[int, int]], int, bool]:
    """Recover valid international numbers that the matcher rejects because more digits follow.

    For each '+' candidate take the longest prefix, cut at digit-group boundaries, that parses as a
    valid number. Candidates the matcher already accepted are skipped: recovery exists only for the
    ones it rejected, and re-parsing every accepted number made a document with a few hundred valid
    numbers exhaust the budget and be reported PARTIAL. Returns (spans, parses still available,
    whether a cap stopped the search early).
    """
    spans: list[tuple[int, int]] = []
    candidates = (c for c in _INTL_CANDIDATE.finditer(window) if c.start() not in accepted_starts)
    for count, cand in enumerate(candidates, start=1):
        if count > _MAX_CANDIDATES:
            return spans, parses_left, True
        text = cand.group()
        for end in reversed([m.end() for m in _DIGIT_RUN.finditer(text)]):
            if parses_left <= 0:
                return spans, 0, True
            parses_left -= 1
            try:
                number = phonenumbers.parse(text[:end], None)
            except phonenumbers.NumberParseException:
                continue
            if phonenumbers.is_valid_number(number):
                spans.append((cand.start(), cand.start() + end))
                break
    return spans, parses_left, False


def _budget_exhausted(matcher: phonenumbers.PhoneNumberMatcher) -> bool:
    """True if the matcher stopped because its try budget ran out, not because the text ended.

    This is the ONLY place that touches the library's private ``_max_tries``; pyproject pins the
    library to a tested range. If an update removes the attribute we cannot verify completeness, so
    we fail safe (raise) rather than report a complete scan. Tests pin the attribute's behaviour
    against real exhaustion.
    """
    remaining = getattr(matcher, "_max_tries", None)
    if remaining is None:
        raise RuntimeError("cannot verify phone search completeness")
    return remaining <= 0
