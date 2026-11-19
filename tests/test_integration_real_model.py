"""End-to-end tests with the real spaCy model (skipped if the model is not installed)."""
import pytest

spacy = pytest.importorskip("spacy")
if not spacy.util.is_package("en_core_web_sm"):
    pytest.skip("en_core_web_sm is not installed", allow_module_level=True)

from pii_engine.engine import default_engine
from pii_engine.segmenter import segment
from pii_engine.types import ScanStatus


@pytest.fixture(scope="module")
def engine():
    return default_engine()


def found(engine, text, **kw):
    result = engine.scan(text, **kw)
    return result.status, [(s.type.value, text[s.start : s.end]) for s in result.spans]


def test_english_all_entity_types(engine):
    text = "Please send the invoice to Emily Carter at emily.carter@example.com, card 4111 1111 1111 1111, or call +44 20 7946 0958."
    status, spans = found(engine, text)
    assert status is ScanStatus.COMPLETE
    assert spans == [
        ("PERSON", "Emily Carter"),
        ("EMAIL", "emily.carter@example.com"),
        ("CREDIT_CARD", "4111 1111 1111 1111"),
        ("PHONE", "+44 20 7946 0958"),
    ]


def test_hebrew_is_partial_and_patterns_still_work(engine):
    status, spans = found(engine, "שלום, אני רוצה לשלוח את החשבונית לדוד כהן, מייל dudu@example.com")
    assert status is ScanStatus.PARTIAL and spans == [("EMAIL", "dudu@example.com")]


def test_one_word_names_are_found_in_both_profiles(engine):
    text = "Call me on (415) 555-2671, thanks. Madonna agreed."
    for profile in ("strict", "balanced"):
        _, spans = found(engine, text, region="US", profile=profile)
        assert ("PERSON", "Madonna") in spans, profile


def test_profiles_differ_on_brand_less_luhn_numbers(engine):
    prefix = "123456781234567"  # no known card brand starts with 12
    check = next(str(d) for d in range(10) if _luhn_ok(prefix + str(d)))
    text = f"ref {prefix}{check} noted"
    _, strict = found(engine, text, profile="strict")
    _, balanced = found(engine, text, profile="balanced")
    assert ("CREDIT_CARD", prefix + check) in strict and not any(t == "CREDIT_CARD" for t, _ in balanced)


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def test_email_only_input_is_complete(engine):
    assert found(engine, "jane.doe@example.com") == (ScanStatus.COMPLETE, [("EMAIL", "jane.doe@example.com")])


def test_name_is_found_whole_exactly_once_around_every_segment_edge(engine):
    """Sampled version of the 258-position offline sweep, with the real model and default settings."""
    base = ("the quarterly report was reviewed and the team agreed to move the deadline to next week "
            "because the budget needs more time. " * 80)[:9000]
    segs = segment(base, 4_000, 200)
    edges = sorted({s.start for s in segs[1:]} | {s.start + len(s.text) for s in segs[:-1]})
    sentence, name = " Please send it to Emily Carter before Friday.", "Emily Carter"
    spaces = [i for i, c in enumerate(base) if c == " " and any(abs(i - e) <= 260 for e in edges)]
    for p in spaces[::9]:
        text = base[:p] + sentence + base[p:]
        start = p + sentence.index(name)
        people = [(s.start, s.end) for s in engine.scan(text).spans if s.type.value == "PERSON"]
        assert people == [(start, start + len(name))], p


def test_long_input_stays_correct_and_complete(engine):
    text = "Yesterday Emily Carter emailed emily.carter@example.com about the contract. " * 400  # ~30k chars
    result = engine.scan(text)
    assert result.status is ScanStatus.COMPLETE
    types = [s.type.value for s in result.spans]
    assert types.count("EMAIL") == 400 and types.count("PERSON") == 400
