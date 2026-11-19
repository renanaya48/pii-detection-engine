"""Profiles, applied through the engine with stub recognizers (no model needed)."""
import pytest

from pii_engine.engine import Engine
from pii_engine.recognizers import IncompleteScan, PhoneRecognizer
from pii_engine.types import EntityType as T
from pii_engine.types import Evidence as E
from pii_engine.types import ScanStatus, Span


class _Fixed:
    name = "fixed"

    def __init__(self, *spans):
        self._spans = list(spans)

    def analyze(self, text, ctx=None):
        return self._spans


def kinds(engine, text, **kw):
    result = engine.scan(text, **kw)
    return [(s.type.value, text[s.start : s.end]) for s in result.spans]


def test_unknown_brand_card_is_strict_only():
    card = Span(T.CREDIT_CARD, 0, 16, E.PATTERN)
    engine = Engine([_Fixed(card)])
    text = "9" * 16
    assert kinds(engine, text, profile="strict") == [("CREDIT_CARD", text)]
    assert kinds(engine, text, profile="balanced") == []


def test_known_brand_card_is_in_both_profiles():
    card = Span(T.CREDIT_CARD, 0, 16, E.CHECKSUM)
    engine = Engine([_Fixed(card)])
    for profile in ("strict", "balanced"):
        assert len(kinds(engine, "4" * 16, profile=profile)) == 1


def test_one_word_names_are_accepted_by_both_built_in_profiles():
    """Regression for a measured mistake: balanced used to drop one-word names, cutting PERSON recall on
    real informal text from 35% to 7% without improving precision (see PROFILE docs in config.py)."""
    one = Span(T.PERSON, 0, 5, E.MODEL)  # "Emily"
    two = Span(T.PERSON, 6, 17, E.MODEL)  # "Anna Carter"
    engine = Engine([_Fixed(one, two)])
    text = "Emily Anna Carter"
    for profile in ("strict", "balanced"):
        assert [t for _, t in kinds(engine, text, profile=profile)] == ["Emily", "Anna Carter"]


def test_the_optional_word_count_rule_still_works_for_callers_who_want_it():
    from dataclasses import replace

    from pii_engine.config import BALANCED

    two_word = replace(BALANCED, name="two-word", person_min_words=2)
    one = Span(T.PERSON, 0, 5, E.MODEL)
    two = Span(T.PERSON, 6, 17, E.MODEL)
    engine = Engine([_Fixed(one, two)], profiles={"two-word": two_word})
    assert [t for _, t in kinds(engine, "Emily Anna Carter", profile="two-word")] == ["Anna Carter"]


def test_rejected_span_cannot_suppress_an_accepted_one():
    """The reason profiles filter BEFORE overlap resolution."""
    long_unknown_card = Span(T.CREDIT_CARD, 0, 16, E.PATTERN)  # would win on length...
    phone = Span(T.PHONE, 2, 12, E.PATTERN)  # ...and drop the phone if filtering came after
    engine = Engine([_Fixed(long_unknown_card, phone)])
    text = "x" * 16
    assert kinds(engine, text, profile="balanced") == [("PHONE", text[2:12])]
    assert kinds(engine, text, profile="strict") == [("CREDIT_CARD", text)]  # strict accepts it, longer wins


def test_profiles_can_be_injected_without_touching_module_state():
    from dataclasses import replace

    from pii_engine.config import BALANCED, PROFILES

    two_word = replace(BALANCED, name="balanced-two-word", person_min_words=2)
    engine = Engine([_Fixed(Span(T.PERSON, 0, 5, E.MODEL))], profiles={**PROFILES, two_word.name: two_word})
    assert len(engine.scan("Emily", profile="balanced").spans) == 1  # the built-in profile is unchanged
    assert engine.scan("Emily", profile="balanced-two-word").spans == ()  # the injected rule applies
    assert "balanced-two-word" not in PROFILES  # the shared mapping was not modified
    assert Engine([_Fixed()]).scan("x", profile="balanced-two-word").status is ScanStatus.FAILED


def test_default_profile_is_balanced():
    card = Span(T.CREDIT_CARD, 0, 16, E.PATTERN)
    assert Engine([_Fixed(card)]).scan("9" * 16).spans == ()


@pytest.mark.parametrize("bad", ["lenient", "", None, 3])
def test_unknown_profile_fails_the_scan(bad):
    assert Engine([_Fixed()]).scan("x", profile=bad).status is ScanStatus.FAILED


class _Incomplete:
    name = "incomplete"

    def analyze(self, text, ctx=None):
        raise IncompleteScan([Span(T.PHONE, 0, 4, E.PATTERN)])


def test_incomplete_recognizer_gives_partial_and_keeps_its_spans():
    engine = Engine([_Incomplete(), _Fixed(Span(T.EMAIL, 5, 9, E.PATTERN))])
    result = engine.scan("0123 abcd")
    assert result.status is ScanStatus.PARTIAL
    assert [s.type for s in result.spans] == [T.PHONE, T.EMAIL]
    assert engine.metrics.snapshot()["recognizer_errors"] == {"incomplete:IncompleteScan": 1}


def test_all_incomplete_is_partial_not_failed():
    assert Engine([_Incomplete()]).scan("0123").status is ScanStatus.PARTIAL


def test_phone_budget_exhaustion_reaches_the_engine_as_partial(monkeypatch):
    monkeypatch.setattr("pii_engine.recognizers.phone._MAX_TRIES", 5)
    engine = Engine([PhoneRecognizer()])
    assert engine.scan("1 2 " * 200).status is ScanStatus.PARTIAL
