"""Payment-card detection: digit groups -> Luhn -> brand prefix/length.

Evidence levels:
* CHECKSUM: Luhn passes AND the number matches a known brand prefix/length.
* PATTERN: Luhn passes but the brand is unknown. A passing Luhn check is only a ~10%
  filter and does not prove the number is a real card, so this weaker tier exists for the
  strict profile to opt into; the balanced profile only surfaces CHECKSUM.

* HEURISTIC: a run whose FIRST group has fewer than 4 digits ("1 2 3 4 5 6 7 3782 8224 6310" ...).
  Real cards start with a full group (4-4-4-4, 4-6-5, ...), so such a run is almost always a
  contaminated window made of unrelated digits in front of a card. About 10% of them pass Luhn by
  chance with a known brand prefix and, being longer, would beat the real card in the merge and
  leave its last digits unreported. Only the strict profile accepts them, and they lose to a real card.
  Not solved (documented limitation): a decoy whose first group is a full 4 digits, e.g. a 20-digit
  run holding two overlapping valid cards, is genuinely ambiguous; one is chosen.

Digit groups may be split by single spaces or hyphens. A window may start at EVERY digit group (so
digits before a card cannot hide it) and spans up to 8 groups / 19 digits; every valid window is
emitted. The recognizer must not pick one itself: a longer run can pass Luhn by chance with weaker
evidence ("378282246310005 101" is a valid Amex followed by digits), and choosing it would
discard the stronger shorter one before the profile filter and the merge could weigh them.

Digits are any Unicode decimal digit (regex class "digit"), normalised to ASCII only for the checksum
and brand tests; spans keep the original offsets. Otherwise fullwidth or Arabic-Indic digits would
evade detection or be mis-scored.
"""
from __future__ import annotations

import time
import unicodedata

import regex

from ..types import EntityType, Evidence, ScanContext, Span
from .base import IncompleteScan, scaled_timeout

_GROUP = regex.compile(r"\d+")  # maximal digit runs, so a window never starts or ends mid-number
_MAX_GROUPS = 8  # groups per window
_SEPARATORS = " -"  # exactly one of these between two groups of the same number
_FULL_GROUP = 4  # a card's first group has at least this many digits
_CHECK_EVERY = 2_048  # groups between deadline checks

# (brand, prefix regex over the digit string, allowed lengths). Ranges follow the public IIN allocations.
_BRANDS = (
    ("visa", regex.compile(r"4"), (13, 16, 19)),
    ("mastercard", regex.compile(r"5[1-5]|2(?:2[2-9][1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720)"), (16,)),
    ("amex", regex.compile(r"3[47]"), (15,)),
    ("discover", regex.compile(r"6011|65|64[4-9]"), (16, 17, 18, 19)),
    ("diners", regex.compile(r"3(?:0[0-5]|[68])"), (14, 15, 16, 17, 18, 19)),
    ("jcb", regex.compile(r"35(?:2[89]|[3-8]\d)"), (16, 17, 18, 19)),
    ("unionpay", regex.compile(r"62"), (16, 17, 18, 19)),
)
_MIN_DIGITS, _MAX_DIGITS = 13, 19


def luhn_valid(digits: str) -> bool:
    total, double = 0, False
    for ch in reversed(digits):
        d = int(ch)  # works for any Unicode decimal digit, not only ASCII
        if double:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        double = not double
    return total % 10 == 0


def _brand_known(digits: str) -> bool:
    return any(p.match(digits) and len(digits) in lengths for _, p, lengths in _BRANDS)


def _ascii_digits(digits: str) -> str:
    return digits if digits.isascii() else "".join(str(unicodedata.decimal(ch)) for ch in digits)


def _classify(digits: str) -> Evidence | None:
    # Cheap length test first (every character is one digit): most windows of a chain are too short,
    # and converting them would be wasted work on dense digit input.
    if not (_MIN_DIGITS <= len(digits) <= _MAX_DIGITS):
        return None
    digits = _ascii_digits(digits)  # brand prefixes and the repeated-digit test are defined on ASCII digits
    if len(set(digits)) == 1 or not luhn_valid(digits):
        return None
    return Evidence.CHECKSUM if _brand_known(digits) else Evidence.PATTERN


class CreditCardRecognizer:
    name = "credit_card"

    def __init__(self, timeout_s: float) -> None:
        self._timeout_s = timeout_s

    def analyze(self, text: str, ctx: ScanContext = ScanContext()) -> list[Span]:
        budget = scaled_timeout(self._timeout_s, text)
        deadline = time.perf_counter() + budget
        try:
            groups = [(m.start(), m.end()) for m in _GROUP.finditer(text, timeout=budget)]
        except TimeoutError:
            raise IncompleteScan([]) from None
        spans: list[Span] = []
        for i in range(len(groups)):
            # The window loop below is plain Python, outside the regex timeout, so it checks the
            # same budget itself and reports what it has so far instead of running unbounded.
            if i % _CHECK_EVERY == 0 and time.perf_counter() > deadline:
                raise IncompleteScan(spans)
            spans.extend(_windows_from(text, groups, i))
        return spans


def _windows_from(text: str, groups: list[tuple[int, int]], i: int) -> list[Span]:
    """Every window that starts at group ``i`` and passes the card tests.

    Only integer lengths are tracked while extending; strings are built just for windows that have a
    plausible digit count, so long runs of tiny groups ("1 1 1 1 ...") stay cheap.
    """
    start, end = groups[i]
    total = end - start  # every character of a group is one digit
    found: list[Span] = []
    first_is_short = total < _FULL_GROUP
    j = i
    while total <= _MAX_DIGITS:
        if total >= _MIN_DIGITS:
            digits = "".join(text[a:b] for a, b in groups[i : j + 1])
            evidence = _classify(digits)
            if evidence is not None:
                if first_is_short and j > i:  # prefix contamination, see the module docstring
                    evidence = Evidence.HEURISTIC
                found.append(Span(EntityType.CREDIT_CARD, start, groups[j][1], evidence))
        if j + 1 >= len(groups) or j + 1 - i >= _MAX_GROUPS:
            break
        next_start, next_end = groups[j + 1]
        if next_start - groups[j][1] != 1 or text[groups[j][1]] not in _SEPARATORS:
            break  # not joined by exactly one space or hyphen
        total += next_end - next_start
        j += 1
    return found
