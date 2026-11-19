"""Engine with the real pattern recognizers (no spaCy model): merge + region handling end to end."""
import pytest

from pii_engine.config import Limits
from pii_engine.engine import Engine
from pii_engine.recognizers import CreditCardRecognizer, EmailRecognizer, PhoneRecognizer
from pii_engine.types import ScanStatus

LIMITS = Limits()
engine = Engine([EmailRecognizer(0.5), CreditCardRecognizer(0.5), PhoneRecognizer()], LIMITS)


def kinds(text, **kw):
    r = engine.scan(text, **kw)
    return r.status, [(s.type.value, text[s.start : s.end]) for s in r.spans]


def test_all_three_types_in_one_text():
    text = "Mail a@b.com, card 4111 1111 1111 1111, phone +44 20 7946 0958."
    status, found = kinds(text)
    assert status is ScanStatus.COMPLETE
    assert found == [
        ("EMAIL", "a@b.com"),
        ("CREDIT_CARD", "4111 1111 1111 1111"),
        ("PHONE", "+44 20 7946 0958"),
    ]


def test_card_wins_over_overlapping_phone_with_region():
    _, found = kinds("pay 4111 1111 1111 1111", region="US")
    assert found == [("CREDIT_CARD", "4111 1111 1111 1111")]


def test_region_is_case_insensitive_and_enables_local_numbers():
    assert kinds("call (415) 555-2671", region="us")[1] == [("PHONE", "(415) 555-2671")]


def test_unsupported_region_code_gives_partial_not_a_crash():
    status, found = kinds("a@b.com (415) 555-2671", region="ZZ")
    assert status is ScanStatus.PARTIAL
    assert found == [("EMAIL", "a@b.com")]


def test_digit_suffixed_international_number_is_strict_only():
    """Documents a trade-off: recovery from trailing digits raises false hits, so balanced skips it."""
    text = "my number +44 20 7946 0958 12"
    assert kinds(text, profile="strict")[1] == [("PHONE", "+44 20 7946 0958")]
    assert kinds(text, profile="balanced")[1] == []


@pytest.mark.parametrize("bad", ["USA", "U", "1S", "", 5])
def test_malformed_region_fails_the_scan(bad):
    assert engine.scan("a@b.com", region=bad).status is ScanStatus.FAILED
