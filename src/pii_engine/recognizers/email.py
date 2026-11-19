from __future__ import annotations

import regex

from ..types import EntityType, Evidence, ScanContext, Span
from .base import IncompleteScan, scaled_timeout

# The lookbehind lets a match start only at the beginning of a local-part run, so a long
# run without '@' is scanned once, not once per character (no quadratic blow-up). Quantifiers
# are bounded to the RFC limits (64-char local part, 63-char labels).
_EMAIL = regex.compile(
    r"(?<![\w.+-])"
    r"[\w.+-]{1,64}"
    r"@"
    r"(?:[\w-]{1,63}\.){1,8}"
    r"(?:xn--[a-z0-9-]{2,59}|[^\W\d_]{2,24})",
)


class EmailRecognizer:
    name = "email"

    def __init__(self, timeout_s: float) -> None:
        self._timeout_s = timeout_s

    def analyze(self, text: str, ctx: ScanContext = ScanContext()) -> list[Span]:
        spans: list[Span] = []
        try:
            for m in _EMAIL.finditer(text, timeout=scaled_timeout(self._timeout_s, text)):
                spans.append(Span(EntityType.EMAIL, m.start(), m.end(), Evidence.PATTERN))
        except TimeoutError:
            raise IncompleteScan(spans) from None  # keep what was found; the scan reports PARTIAL
        return spans
