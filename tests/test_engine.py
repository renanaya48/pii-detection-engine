"""Engine behaviour with stub recognizers (no model needed)."""
import time

from pii_engine.config import Limits
from pii_engine.engine import Engine
from pii_engine.recognizers import EmailRecognizer
from pii_engine.types import EntityType, Evidence, ScanStatus, Span


class _Boom:
    name = "boom"

    def analyze(self, text, ctx=None):
        raise RuntimeError(f"secret in message: {text}")


class _Fixed:
    name = "fixed"

    def __init__(self, *spans):
        self._spans = list(spans)

    def analyze(self, text, ctx=None):
        return self._spans


def test_all_recognizers_ok_is_complete():
    engine = Engine([_Fixed(Span(EntityType.PERSON, 0, 3, Evidence.MODEL))])
    result = engine.scan("Bob", profile="strict")
    assert result.status is ScanStatus.COMPLETE and len(result.spans) == 1


def test_one_failing_recognizer_gives_partial_and_keeps_other_findings():
    engine = Engine([_Boom(), _Fixed(Span(EntityType.PERSON, 0, 3, Evidence.MODEL))])
    result = engine.scan("Bob", profile="strict")
    assert result.status is ScanStatus.PARTIAL
    assert len(result.spans) == 1


def test_all_failing_is_failed_and_error_metric_has_no_input_text():
    engine = Engine([_Boom()])
    result = engine.scan("my-secret-text")
    assert result.status is ScanStatus.FAILED
    snapshot = repr(engine.metrics.snapshot())
    assert "my-secret-text" not in snapshot and "secret" not in snapshot
    assert "boom:RuntimeError" in snapshot


def test_oversized_and_non_string_input_fail_without_raising():
    engine = Engine([_Fixed()], Limits(max_chars=10))
    assert engine.scan("x" * 11).status is ScanStatus.FAILED
    assert engine.scan(None).status is ScanStatus.FAILED  # type: ignore[arg-type]
    assert engine.scan(b"bytes").status is ScanStatus.FAILED  # type: ignore[arg-type]


def test_regex_timeout_makes_scan_partial_not_a_hang():
    class _Slow(EmailRecognizer):
        def analyze(self, text, ctx=None):
            import regex

            regex.search(r"(?:a|aa)+b", text, timeout=0.01)  # exponential pattern, bounded by timeout
            return []

    engine = Engine([_Slow(0.01), _Fixed()])
    started = time.perf_counter()
    result = engine.scan("a" * 60)
    assert result.status is ScanStatus.PARTIAL
    assert time.perf_counter() - started < 1.0
    assert engine.metrics.snapshot()["recognizer_errors"] == {"email:TimeoutError": 1}


def test_metrics_count_types_only():
    engine = Engine([_Fixed(Span(EntityType.EMAIL, 0, 3, Evidence.PATTERN))])
    engine.scan("abc")
    snap = engine.metrics.snapshot()
    assert snap["entities"] == {"EMAIL": 1} and snap["scans"] == 1
