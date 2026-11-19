"""The synthetic generator must be deterministic, label correctly, and keep dev and test STRUCTURALLY apart."""
import re

import phonenumbers
import pytest

from evaluation.synthetic import POOLS, TEMPLATES, build_split, SEEDS

DEV, TEST = build_split("dev"), build_split("test")


def surfaces(record):
    return [(g["type"], record["text"][g["start"] : g["end"]]) for g in record["gold"]]


def luhn(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def test_generation_is_deterministic():
    assert build_split("dev") == DEV and build_split("test") == TEST


def test_different_seeds_per_split():
    assert SEEDS["dev"] != SEEDS["test"]


def test_gold_offsets_slice_to_non_empty_text_inside_the_record():
    for record in DEV + TEST:
        for g in record["gold"]:
            assert 0 <= g["start"] < g["end"] <= len(record["text"]) and record["text"][g["start"] : g["end"]].strip()


def test_dev_and_test_share_no_templates():
    for group, by_split in TEMPLATES.items():
        assert not set(by_split["dev"]) & set(by_split["test"]), group


def test_dev_and_test_share_no_names_domains_places_or_other_pools():
    dev, test = POOLS["dev"], POOLS["test"]
    for field in ("first", "last", "domains", "places", "orgs", "products", "es_first", "es_last", "fr_first", "fr_last", "he_names",
                  "email_styles", "card_styles", "negatives", "other_card_prefixes", "id_prefixes", "phone_suffixes", "chain_styles"):
        assert not set(getattr(dev, field)) & set(getattr(test, field)), field
    assert set(dev.person_styles) & set(test.person_styles) == {"full"}  # the only deliberately shared style


def test_test_split_has_held_out_formats_dev_never_contains():
    dev_text = " ".join(r["text"] for r in DEV)
    assert not re.search(r"\b\d{16}\b", dev_text)  # unbroken card numbers: test only
    assert not re.search(r"\d{4}-\d{4}-\d{4}-\d{4}", dev_text)  # hyphenated cards: test only
    dev_people = [s for r in DEV for t, s in surfaces(r) if t == "PERSON"]
    assert not any(p.isupper() or p.islower() for p in dev_people if p.isascii())  # lower/ALL CAPS names: test only
    test_people = [s for r in TEST for t, s in surfaces(r) if t == "PERSON" and s.isascii()]
    assert any(p.isupper() for p in test_people) and any(p.islower() for p in test_people)


def test_every_group_has_equal_records_in_both_splits():
    from collections import Counter

    assert Counter(r["group"] for r in DEV) == Counter(r["group"] for r in TEST)


def test_cards_in_card_groups_are_luhn_valid_and_negatives_are_not_labelled():
    for record in DEV + TEST:
        for kind, text in surfaces(record):
            if kind == "CREDIT_CARD":
                digits = re.sub(r"\D", "", text)
                assert luhn(digits) and 15 <= len(digits) <= 16, text
        if record["group"].startswith("negative"):
            assert record["gold"] == []


def test_profile_exercising_groups_have_the_properties_they_claim():
    """These groups exist so strict and balanced can be told apart; check each really is what it says."""
    for records in (DEV, TEST):
        groups = {r["group"]: [] for r in records}
        for r in records:
            groups[r["group"]].append(r)
        for r in groups["card_other_brand"]:  # real, Luhn-valid, brand unknown to the engine
            (_, text), = surfaces(r)
            digits = re.sub(r"\D", "", text)
            assert luhn(digits) and len(digits) == 16 and not re.match(r"4|5[1-5]|3[47]|6011|65|62|2(2[2-9]|[3-6]|7[01])", digits)
        for r in groups["negative_luhn_ids"]:  # pass Luhn, no known prefix, and are not labelled
            digits = re.search(r"\d[\d -]{14,}\d", r["text"]).group().replace(" ", "").replace("-", "")
            assert luhn(digits) and len(digits) == 16 and r["gold"] == []
            assert not re.match(r"4|5[1-5]|3[47]|6011|65|62", digits)
        for r in groups["phone_digit_suffix"]:  # the number is gold; the digits after it are not
            (_, number), = surfaces(r)
            assert r["text"][r["gold"][0]["end"]] == " " and r["text"][r["gold"][0]["end"] + 1].isdigit()
            assert phonenumbers.is_valid_number(phonenumbers.parse(number, None))
        for r in groups["negative_plus_chains"]:
            assert r["gold"] == [] and "+" in r["text"]


def test_luhn_invalid_negatives_really_fail_luhn():
    from evaluation.synthetic import card

    import random

    rnd = random.Random(0)
    for _ in range(200):
        assert not luhn(re.sub(r"\D", "", card(rnd, POOLS["test"], valid=False)))


def test_phone_gold_is_a_valid_number_in_its_region():
    for record in DEV + TEST:
        for kind, text in surfaces(record):
            if kind != "PHONE":
                continue
            if text.startswith("+"):
                assert phonenumbers.is_valid_number(phonenumbers.parse(text, None)), text
            else:
                assert record["group"].startswith("phone_national")


def test_region_hint_is_given_only_to_the_group_that_tests_it():
    for record in DEV + TEST:
        has_hint = record["region"] is not None
        assert has_hint == (record["group"] == "phone_national_with_region"), record["group"]


def test_non_english_groups_expect_partial_and_others_do_not():
    for record in DEV + TEST:
        assert (record["expected_status"] == "partial") == record["group"].startswith("nonenglish")


def test_titles_are_not_part_of_the_person_span():
    titled = [r for r in DEV if "Dr. " in r["text"]]
    assert titled
    for record in titled:
        for kind, text in surfaces(record):
            assert not text.startswith("Dr.")


@pytest.mark.parametrize("split_records", [DEV, TEST])
def test_ids_are_unique(split_records):
    ids = [r["id"] for r in split_records]
    assert len(ids) == len(set(ids))
