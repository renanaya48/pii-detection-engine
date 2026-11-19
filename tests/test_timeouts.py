"""Regex timeouts must keep findings and scale with input size (found in a loaded benchmark run)."""
import pytest

from pii_engine.config import Limits
from pii_engine.engine import Engine
from pii_engine.recognizers import CreditCardRecognizer, EmailRecognizer, IncompleteScan
from pii_engine.recognizers.base import scaled_timeout
from pii_engine.types import ScanContext, ScanStatus

CTX = ScanContext()


class _TimesOutAfter:
    """Wraps a compiled pattern: yields ``after`` real matches, then raises TimeoutError like regex does."""

    def __init__(self, real, after):
        self._real, self._after = real, after

    def finditer(self, text, timeout):
        for i, match in enumerate(self._real.finditer(text, timeout=timeout)):
            if i == self._after:
                raise TimeoutError
            yield match


def test_email_timeout_keeps_the_findings_made_so_far(monkeypatch):
    from pii_engine.recognizers import email

    monkeypatch.setattr(email, "_EMAIL", _TimesOutAfter(email._EMAIL, after=2))
    text = "a@b.co c@d.co e@f.co g@h.co"
    with pytest.raises(IncompleteScan) as info:
        EmailRecognizer(0.5).analyze(text, CTX)
    assert [text[s.start : s.end] for s in info.value.spans] == ["a@b.co", "c@d.co"]


def test_engine_reports_partial_but_still_returns_the_email_found_before_the_timeout(monkeypatch):
    from pii_engine.recognizers import email

    monkeypatch.setattr(email, "_EMAIL", _TimesOutAfter(email._EMAIL, after=2))
    text = "a@b.co c@d.co e@f.co"
    result = Engine([EmailRecognizer(0.5)]).scan(text)
    assert result.status is ScanStatus.PARTIAL
    assert [text[s.start : s.end] for s in result.spans] == ["a@b.co", "c@d.co"]


def test_card_deadline_keeps_the_findings_made_so_far(monkeypatch):
    """The window loop is plain Python, so it checks the time budget itself; a fake clock makes it deterministic."""
    import types

    from pii_engine.recognizers import credit_card

    ticks = iter([0.0, 0.0] + [999.0] * 100)  # deadline computed, first check on time, then far past it
    monkeypatch.setattr(credit_card, "time", types.SimpleNamespace(perf_counter=lambda: next(ticks)))
    text = "4111111111111111 " + "12 x " * 2_100  # > 2,048 digit groups, so a second check happens
    with pytest.raises(IncompleteScan) as info:
        CreditCardRecognizer(0.5).analyze(text, CTX)
    assert [text[s.start : s.end] for s in info.value.spans] == ["4111111111111111"]


def test_card_grouping_stage_timeout_is_reported_as_incomplete(monkeypatch):
    from pii_engine.recognizers import credit_card

    monkeypatch.setattr(credit_card, "_GROUP", _TimesOutAfter(credit_card._GROUP, after=1))
    with pytest.raises(IncompleteScan):
        CreditCardRecognizer(0.5).analyze("4111111111111111 5555555555554444", CTX)


def test_timeout_budget_scales_with_input_length():
    base = 0.05
    assert scaled_timeout(base, "x" * 500) == base
    assert scaled_timeout(base, "x" * 10_000) == base
    assert scaled_timeout(base, "x" * 50_000) == pytest.approx(5 * base)
    assert scaled_timeout(base, "x" * 100_000) == pytest.approx(10 * base)  # hostile input stays bounded


@pytest.mark.parametrize(
    "unit,recognizer",
    [("a@b.co ", EmailRecognizer), ("4111 1111 1111 1111 ", CreditCardRecognizer)],
)
def test_dense_valid_input_at_the_cap_is_complete_with_the_default_timeout(unit, recognizer):
    """Regression: with a fixed 50 ms budget this lost every finding (or varied with machine load)."""
    limits = Limits()
    text = (unit * (limits.max_chars // len(unit) + 1))[: limits.max_chars]
    result = Engine([recognizer(limits.regex_timeout_s)], limits).scan(text, profile="strict")
    assert result.status is ScanStatus.COMPLETE
    assert len(result.spans) >= limits.max_chars // len(unit) // 2  # essentially all of them


def test_hostile_input_is_still_bounded_by_the_scaled_budget():
    import time

    hostile = "a@" * 50_000
    started = time.perf_counter()
    Engine([EmailRecognizer(0.05)]).scan(hostile)
    assert time.perf_counter() - started < 1.5
