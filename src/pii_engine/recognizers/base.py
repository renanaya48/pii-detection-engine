from __future__ import annotations

from typing import Protocol

from ..types import ScanContext, Span


class IncompleteScan(Exception):
    """Raised by a recognizer that had to stop searching early (e.g. a search budget ran out).

    Carries the spans found before stopping so they are not lost; the engine keeps them and
    marks the scan PARTIAL, because "nothing found" can no longer be read as "nothing there".
    """

    def __init__(self, spans: list[Span]) -> None:
        super().__init__("recognizer stopped before finishing")
        self.spans = spans


def scaled_timeout(base_s: float, text: str, per_chars: int = 10_000) -> float:
    """Regex time budget for ``text``: ``base_s`` covers ``per_chars`` characters, longer text gets
    proportionally more. A fixed budget over 100k characters of dense but valid input was too tight
    (and made detection depend on machine load); a hostile input is still bounded, at 10x the base."""
    return base_s * max(1.0, len(text) / per_chars)


class Recognizer(Protocol):
    """A plugin that finds one kind of entity. New entity types are new recognizers, not core changes."""

    name: str

    def analyze(self, text: str, ctx: ScanContext) -> list[Span]:
        """Return spans over ``text`` as half-open code-point ranges.

        May raise ``IncompleteScan`` (partial results) or any other exception; the engine isolates both.
        """
        ...
