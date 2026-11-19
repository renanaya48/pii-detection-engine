"""Language gating in the engine, using stub recognizers (no model needed).

Policy under test:
  English   -> NER runs, COMPLETE
  Mixed     -> NER runs on the whole text, PARTIAL (non-English parts are not covered)
  Other     -> NER skipped, PARTIAL (pattern recognizers still run)
  Uncertain -> NER runs best-effort, PARTIAL (running the English model proves nothing about the language)
  No text   -> NER skipped, COMPLETE (no letters: nothing for NER to find)
"""
import pytest

from pii_engine.engine import Engine
from pii_engine.recognizers import EmailRecognizer
from pii_engine.types import EntityType as T
from pii_engine.types import Evidence as E
from pii_engine.types import ScanStatus, Span


class _EnglishOnlyStub:
    name = "ner"
    requires_english = True

    def __init__(self):
        self.calls = 0

    def analyze(self, text, ctx=None):
        self.calls += 1
        return [Span(T.PERSON, 0, 5, E.MODEL)]


def make():
    ner = _EnglishOnlyStub()
    return Engine([EmailRecognizer(0.5), ner]), ner


def test_english_runs_ner_and_is_complete():
    engine, ner = make()
    result = engine.scan("Please send the invoice to Emily Carter, thanks", profile="strict")
    assert ner.calls == 1 and result.status is ScanStatus.COMPLETE


@pytest.mark.parametrize(
    "text",
    ["שלום, אני רוצה לשלוח את החשבונית לדוד כהן עד יום שישי", "Ayer llamó a Carlos para hablar del contrato y de los pagos."],
)
def test_other_language_skips_ner_reports_partial_and_still_runs_patterns(text):
    engine, ner = make()
    result = engine.scan(text + " a@b.com", profile="strict")
    assert ner.calls == 0
    assert result.status is ScanStatus.PARTIAL
    assert [s.type for s in result.spans] == [T.EMAIL]  # language-independent recognizers still ran
    assert engine.metrics.snapshot()["recognizer_skips"] == {"ner:language": 1}


def test_mixed_language_runs_ner_on_the_whole_text_but_is_partial():
    engine, ner = make()
    text = "Please send the invoice to Emily. Ayer llamó a Carlos para hablar del contrato y de los pagos."
    result = engine.scan(text, profile="strict")
    assert ner.calls == 1 and result.status is ScanStatus.PARTIAL


@pytest.mark.parametrize("text", ["Emily Carter", "María García", "Order ID 123456"])
def test_uncertain_language_runs_ner_best_effort_and_is_partial(text):
    engine, ner = make()
    result = engine.scan(text, profile="strict")
    assert ner.calls == 1 and result.status is ScanStatus.PARTIAL


@pytest.mark.parametrize("text", ["jane@example.com", "+44 20 7946 0958", "4111 1111 1111 1111", ""])
def test_text_without_letters_skips_ner_and_stays_complete(text):
    engine, ner = make()
    result = engine.scan(text, profile="strict")
    assert ner.calls == 0 and result.status is ScanStatus.COMPLETE
    assert engine.metrics.snapshot()["recognizer_skips"] == {}  # not an unsupported-language skip


@pytest.mark.parametrize("text", ["Alice<alice@example.com>", "Alice,alice@example.com", "(Alice alice@example.com)"])
def test_a_name_stuck_to_an_email_is_not_mistaken_for_no_text(text):
    engine, ner = make()
    result = engine.scan(text, profile="strict")
    assert ner.calls == 1  # NER runs on the name (uncertain language)...
    assert result.status is ScanStatus.PARTIAL  # ...and the scan says so, instead of claiming complete


def test_a_non_english_name_stuck_to_an_email_skips_ner_and_is_partial_not_complete():
    engine, ner = make()
    result = engine.scan("李伟<email@example.com>", profile="strict")
    assert ner.calls == 0 and result.status is ScanStatus.PARTIAL
    assert [s.type for s in result.spans] == [T.EMAIL]


def test_skipped_recognizer_does_not_count_as_failure():
    only_ner = Engine([_EnglishOnlyStub()])
    result = only_ner.scan("Ayer llamó a Carlos para hablar del contrato y de los pagos.")
    assert result.status is ScanStatus.PARTIAL  # nothing could run, but that is not a crash


def test_language_check_is_skipped_when_no_recognizer_needs_it(monkeypatch):
    def boom(_text):
        raise AssertionError("detect should not be called")

    monkeypatch.setattr("pii_engine.engine.detect", boom)
    assert Engine([EmailRecognizer(0.5)]).scan("a@b.com").status is ScanStatus.COMPLETE
