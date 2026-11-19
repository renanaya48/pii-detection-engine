import time

import pytest

from pii_engine.recognizers.credit_card import CreditCardRecognizer, luhn_valid
from pii_engine.types import Evidence

rec = CreditCardRecognizer(timeout_s=0.5)


def found(text):
    return [(text[s.start : s.end], s.evidence) for s in rec.analyze(text)]


def with_check_digit(prefix: str) -> str:
    """Append the digit that makes ``prefix`` Luhn-valid (used to build brand-less test numbers)."""
    return next(prefix + str(d) for d in range(10) if luhn_valid(prefix + str(d)))


@pytest.mark.parametrize(
    "number",
    [
        "4111111111111111",  # Visa
        "4012888888881881",  # Visa
        "5555555555554444",  # Mastercard
        "2221000000000009",  # Mastercard 2-series
        "378282246310005",  # Amex (15)
        "6011111111111117",  # Discover
        "3530111333300000",  # JCB
        "30569309025904",  # Diners (14)
        "4222222222222",  # Visa (13)
    ],
)
def test_known_brand_with_valid_luhn_is_checksum_evidence(number):
    assert found(f"card {number} on file") == [(number, Evidence.CHECKSUM)]


@pytest.mark.parametrize("sep", [" ", "-"])
def test_grouped_formats(sep):
    number = sep.join(["4111", "1111", "1111", "1111"])
    assert found(f"pay with {number}.") == [(number, Evidence.CHECKSUM)]


def test_amex_4_6_5_grouping():
    assert found("3782 822463 10005")[0][0] == "3782 822463 10005"


def test_card_followed_by_expiry_still_matches_the_card_only():
    assert found("card 4111 1111 1111 1111 12/26") == [("4111 1111 1111 1111", Evidence.CHECKSUM)]


def test_two_cards_in_one_chain_are_both_found():
    spans = found("4111111111111111 5555555555554444")
    assert [s for s, _ in spans] == ["4111111111111111", "5555555555554444"]


@pytest.mark.parametrize(
    "text",
    [
        "4111111111111112",  # Luhn fails
        "0000000000000000",  # repeated digit, Luhn-valid
        "1111111111111111",
        "411111111111",  # 12 digits: too short
        "41111111111111111111",  # 20 digits: too long, no valid window
        "order 1234 5678",  # too few digits
        "call 555-123-4567",
        "2024-05-17 10:30:45",
    ],
)
def test_rejects_non_cards(text):
    assert found(text) == []


def test_not_matched_inside_a_longer_digit_run():
    assert found("9" + "4111111111111111" + "9") == []


def test_luhn_valid_but_unknown_brand_is_only_pattern_evidence():
    number = with_check_digit("900000000000000")
    assert found(number) == [(number, Evidence.PATTERN)]


def test_offsets_are_code_points():
    text = "💳 4111111111111111"
    span = rec.analyze(text)[0]
    assert text[span.start : span.end] == "4111111111111111"


VALID_CARDS = ["378282246310005", "4111111111111111", "5555555555554444", "6011111111111117", "30569309025904"]


def test_valid_card_survives_a_digit_suffix_through_the_balanced_profile():
    """Regression: '378282246310005 101' used to return nothing (a weaker, longer run replaced the card)."""
    from pii_engine.engine import Engine

    engine = Engine([CreditCardRecognizer(0.5)])
    text = "378282246310005 101"
    result = engine.scan(text, profile="balanced")
    assert [text[s.start : s.end] for s in result.spans] == ["378282246310005"]


@pytest.mark.parametrize("suffix", [f" {n}" for n in range(0, 1000, 37)] + ["-1", " 2026", " 12/26", "-0000"])
def test_no_digit_suffix_can_hide_a_valid_card(suffix):
    """Sweep many suffixes: the failure depends on whether the longer run happens to pass Luhn."""
    from pii_engine.engine import Engine

    engine = Engine([CreditCardRecognizer(0.5)])
    for number in VALID_CARDS:
        text = f"card {number}{suffix} thanks"
        spans = engine.scan(text, profile="balanced").spans
        start = text.index(number)
        # Never dropped: some finding covers every digit of the card. Brands with several allowed
        # lengths (Visa, Diners, Discover) may legitimately report the longer valid run, which
        # over-covers by the suffix; that is a larger span, not a miss.
        assert any(s.start <= start and s.end >= start + len(number) for s in spans), (number, suffix)
        if number[:2] in ("37", "55"):  # Amex (15) and Mastercard (16) have a single valid length
            assert [(s.start, s.end) for s in spans] == [(start, start + len(number))], (number, suffix)


PREFIXES = ["", "1", "1 2", "12 34", "ref 12-34-56-78-90", "1 2 3 4 5 6", "1 2 3 4 5 6 7", "1 2 3 4 5 6 7 8", "9 " * 9, "123 456 789 012", "0-1-2-3-4-5-6-7-8-9-0-1"]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("sep", [" ", "-"])
@pytest.mark.parametrize("profile", ["balanced", "strict"])
def test_digit_groups_before_a_card_cannot_hide_it(prefix, sep, profile):
    """Regression: '1 2 3 4 5 6 4111 1111 1111 1111' returned nothing (the card straddled two chains)."""
    from pii_engine.engine import Engine

    engine = Engine([CreditCardRecognizer(0.5)])
    for number in VALID_CARDS:
        grouped = sep.join(number[i : i + 4] for i in range(0, len(number), 4))
        text = f"{prefix} {grouped} thanks" if prefix else f"{grouped} thanks"
        start = text.index(grouped)
        spans = engine.scan(text, profile=profile).spans
        assert any(s.start <= start and s.end >= start + len(grouped) for s in spans), (prefix, grouped, profile)


@pytest.mark.parametrize("prefix", ["1 2 3 4 5 6 7", "12 34 56", "1 2 3", "9 8 7 6 5 4 3 2"])
def test_a_contaminated_decoy_cannot_beat_the_real_card(prefix):
    """The failure behind the earlier prefix bug: '4 5 6 7 3782 8224 6310' passes Luhn by chance (about
    10% of the time), is longer than the real card and used to win the tie, exposing its last digits.
    Runs that start with a short group now carry the lowest evidence, so the real card always wins."""
    from pii_engine.engine import Engine

    engine = Engine([CreditCardRecognizer(0.5)])
    for number in VALID_CARDS:
        grouped = " ".join(number[i : i + 4] for i in range(0, len(number), 4))
        text = f"{prefix} {grouped} thanks"
        start = text.index(grouped)
        for profile in ("balanced", "strict"):
            spans = engine.scan(text, profile=profile).spans
            assert [(s.start, s.end) for s in spans] == [(start, start + len(grouped))], (prefix, grouped, profile)


@pytest.mark.xfail(strict=True, reason="documented limitation: two overlapping valid cards with a full first group are ambiguous")
def test_known_limitation_ambiguous_twenty_digit_run_can_leave_the_last_group_unreported():
    """'4008 4111 1111 1111' is itself a Luhn-valid Visa, so the 20-digit run holds two overlapping valid
    cards. The earlier start wins, reporting (0, 19), and the intended card's last group is not covered.

    The assertion is about the INTENDED card only: groups 2-5, from index 5 to the end of the text. (The
    whole 20-digit run is longer than any card, so asking for it would keep failing even after the engine
    improved.) strict=True: when the engine does cover that card this test starts failing, which is the
    signal to remove it and update SUBMISSION.md."""
    from pii_engine.engine import Engine

    text = "4008 4111 1111 1111 1111"
    intended_start = text.index("4111")  # the card is groups 2-5: (5, 24)
    spans = Engine([CreditCardRecognizer(0.5)]).scan(text, profile="balanced").spans
    assert any(s.start <= intended_start and s.end >= len(text) for s in spans)


def test_documented_limit_a_card_written_one_digit_per_group_is_not_detected():
    """A window spans at most 8 digit groups, so '4 1 1 1 ...' (16 groups) is missed even in strict.
    Not extended on purpose (such a layout is rare and wider windows raise false positives and cost);
    this test records the limit so changing it is a conscious decision."""
    from pii_engine.engine import Engine

    engine = Engine([CreditCardRecognizer(0.5)])
    text = "4 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1"
    assert engine.scan(text, profile="strict").spans == () and engine.scan(text, profile="balanced").spans == ()
    # Eight groups of two digits is within the limit; the short first group makes it strict-only.
    grouped = "41 11 11 11 11 11 11 11"
    assert len(engine.scan(grouped, profile="strict").spans) == 1
    assert engine.scan(grouped, profile="balanced").spans == ()


def test_runs_starting_with_a_short_group_get_the_lowest_evidence():
    spans = rec.analyze("1 2 3 4 5 6 7 3782 8224 6310 005")
    by_text = {s.start: s.evidence for s in spans}
    real = [s for s in spans if s.evidence is Evidence.CHECKSUM]
    assert len(real) == 1 and real[0].start == len("1 2 3 4 5 6 7 ")
    assert all(s.evidence is Evidence.HEURISTIC for s in spans if s.start < real[0].start)
    assert by_text


def test_card_with_digit_groups_on_both_sides_is_found():
    from pii_engine.engine import Engine

    text = "order 12 34 56 78 90 card 4111 1111 1111 1111 12 34 56 78 90 end"
    start = text.index("4111")
    spans = Engine([CreditCardRecognizer(0.5)]).scan(text, profile="balanced").spans
    assert any(s.start <= start and s.end >= start + 19 for s in spans)


def test_recognizer_emits_every_valid_run_and_leaves_the_choice_to_the_engine():
    spans = rec.analyze("378282246310005 101")
    assert {(s.evidence, s.end - s.start) for s in spans} >= {(Evidence.CHECKSUM, 15)}
    assert len(spans) >= 1


def _in_script(number: str, zero: int) -> str:
    return "".join(chr(zero + int(c)) for c in number)


@pytest.mark.parametrize("zero", [0xFF10, 0x0660, 0x06F0, 0x0966, 0x09E6])  # fullwidth, Arabic-Indic, Persian, Devanagari, Bengali
def test_non_ascii_digits_are_detected_with_the_same_evidence_and_original_offsets(zero):
    for number in VALID_CARDS:
        text = f"💳 {_in_script(number, zero)}"
        spans = rec.analyze(text)
        assert [(text[s.start : s.end], s.evidence) for s in spans] == [(_in_script(number, zero), Evidence.CHECKSUM)]


def test_non_ascii_digit_card_is_not_hidden_in_the_balanced_profile():
    from pii_engine.engine import Engine

    text = _in_script("4111111111111111", 0xFF10)
    assert len(Engine([CreditCardRecognizer(0.5)]).scan(text, profile="balanced").spans) == 1


def test_mixed_script_digits_and_repeated_digit_rule_use_values_not_characters():
    mixed = "4111" + _in_script("1111", 0x0660) + "1111" + _in_script("1111", 0xFF10)
    assert [s.evidence for s in rec.analyze(mixed)] == [Evidence.CHECKSUM]
    assert rec.analyze(_in_script("1111111111111111", 0xFF10) + "") == []  # all the same digit, any script
    assert rec.analyze("1111" + _in_script("1111", 0x0660) + "11111111") == []  # same digit, mixed scripts


def test_adversarial_digit_inputs_are_bounded():
    for payload in ["1" * 100_000, "1 " * 50_000, "1-" * 50_000, ("4111 " * 20_000)]:
        t0 = time.perf_counter()
        rec.analyze(payload)
        assert time.perf_counter() - t0 < 2.0
