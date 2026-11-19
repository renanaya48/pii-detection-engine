import pytest

from evaluation.metrics import ALL, Counts, FalsePositiveRate, Mention, aggregate, bootstrap_ci, score_document

E = "EMAIL"
P = "PERSON"


def M(t, s, e):
    return Mention(t, s, e)


def test_exact_match_scores_one_everywhere():
    c = score_document([M(E, 0, 5)], [M(E, 0, 5)])[E]
    assert (c.precision, c.recall, c.f1, c.coverage_recall, c.overlap_precision) == (1, 1, 1, 1, 1)


def test_wrong_type_gets_no_credit_and_counts_as_fp_and_fn():
    doc = score_document([M(E, 0, 5)], [M(P, 0, 5)])
    assert doc[E].recall == 0 and doc[E].coverage_recall == 0
    assert doc[P].precision == 0 and doc[P].overlap_precision == 0


def test_oversized_prediction_is_wrong_exactly_but_covers_and_overlaps():
    c = score_document([M(E, 2, 6)], [M(E, 0, 9)])[E]
    assert c.exact_tp == 0 and c.coverage_recall == 1 and c.overlap_precision == 1


def test_prediction_one_character_short_is_not_covered():
    """The leak case: the span stops a digit early, so the gold entity is NOT covered."""
    c = score_document([M("CREDIT_CARD", 0, 16)], [M("CREDIT_CARD", 0, 15)])["CREDIT_CARD"]
    assert c.coverage_recall == 0 and c.recall == 0 and c.overlap_precision == 1


def test_adjacent_predictions_together_cover_a_gold_span_without_matching_it_exactly():
    c = score_document([M(P, 0, 10)], [M(P, 0, 4), M(P, 4, 10)])[P]
    assert c.coverage_recall == 1 and c.exact_tp == 0


def test_a_gap_between_predictions_breaks_coverage():
    c = score_document([M(P, 0, 10)], [M(P, 0, 4), M(P, 5, 10)])[P]
    assert c.coverage_recall == 0


def test_coverage_is_never_below_exact_recall_and_overlap_never_below_exact_precision():
    import random

    rnd = random.Random(1)
    for _ in range(200):
        gold = [M(E, s := rnd.randint(0, 50), s + rnd.randint(1, 10)) for _ in range(rnd.randint(0, 5))]
        pred = [M(E, s := rnd.randint(0, 50), s + rnd.randint(1, 10)) for _ in range(rnd.randint(0, 5))]
        c = score_document(gold, pred).get(E, Counts())
        assert c.covered >= c.exact_tp and c.overlap_pred >= c.exact_tp


def test_marking_the_whole_document_gets_perfect_coverage_but_is_exposed_by_over_marking():
    """The degenerate engine the review warned about: coverage recall alone would reward it."""
    text_len = 1_000
    gold = [M(E, 100, 120), M(E, 500, 530)]
    c = score_document(gold, [M(E, 0, text_len)])[E]
    assert c.coverage_recall == 1 and c.coverage_recall_any_type == 1
    assert c.precision == 0 and c.f1 == 0  # exact metrics reject it
    assert c.excess_rate == pytest.approx(1 - 50 / 1000) and c.over_marking == pytest.approx(1000 / 50)


def test_exactly_right_spans_have_no_excess():
    c = score_document([M(E, 2, 8)], [M(E, 2, 8)])[E]
    assert c.excess_chars == 0 and c.excess_rate == 0 and c.over_marking == 1


def test_excess_counts_each_character_once_even_when_predictions_overlap():
    c = score_document([M(E, 10, 20)], [M(E, 0, 15), M(E, 10, 25)])[E]
    assert c.pred_chars == 25 and c.excess_chars == 15  # union 0-25 minus gold 10-20


def test_several_predictions_on_one_gold_span_count_as_one_overlap_hit():
    c = score_document([M(P, 0, 10)], [M(P, 0, 4), M(P, 3, 8), M(P, 5, 10)])[P]
    assert c.pred == 3 and c.overlap_pred == 1 and c.overlap_precision == pytest.approx(1 / 3)


def test_one_to_one_prefers_the_exact_pair_over_a_bigger_overlap():
    gold = [M(P, 0, 4), M(P, 2, 10)]  # overlapping gold, as can happen in noisy labels
    c = score_document(gold, [M(P, 0, 4)])[P]
    assert c.exact_tp == 1 and c.overlap_pred == 1


def test_wrong_label_does_not_count_as_same_type_coverage_but_is_visible_as_any_type_coverage():
    c = score_document([M("CREDIT_CARD", 0, 16)], [M("PHONE", 0, 16)])
    assert c["CREDIT_CARD"].coverage_recall == 0 and c["CREDIT_CARD"].coverage_recall_any_type == 1
    assert c["PHONE"].precision == 0 and c["PHONE"].excess_chars == 16  # the PHONE label is wrong text


def test_any_type_coverage_can_combine_predictions_of_different_types():
    c = score_document([M(P, 0, 10)], [M(E, 0, 5), M("PHONE", 5, 10)])[P]
    assert c.coverage_recall == 0 and c.coverage_recall_any_type == 1


def test_empty_denominators_are_none_not_zero():
    only_pred = score_document([], [M(E, 0, 3)])[E]
    assert only_pred.recall is None and only_pred.coverage_recall is None and only_pred.precision == 0
    only_gold = score_document([M(E, 0, 3)], [])[E]
    assert only_gold.precision is None and only_gold.recall == 0
    assert Counts().precision is None and Counts().f1 is None  # nothing predicted AND nothing to find


def test_missing_every_gold_entity_is_f1_zero_not_undefined():
    """Review finding: a system that finds nothing (patterns-only on PERSON) must score 0, not 'n/a'."""
    only_gold = score_document([M(E, 0, 3)], [])[E]
    assert only_gold.f1 == 0
    assert aggregate([score_document([M(P, 0, 5), M(P, 9, 12)], [])])[P].f1 == 0


def test_f1_is_zero_when_nothing_matches_but_both_sides_exist():
    assert Counts(gold=2, pred=2, exact_tp=0).f1 == 0


def test_f1_equals_the_harmonic_mean_of_precision_and_recall_wherever_both_exist():
    import random

    rnd = random.Random(2)
    for _ in range(300):
        gold, pred = rnd.randint(1, 30), rnd.randint(1, 30)
        c = Counts(gold=gold, pred=pred, exact_tp=rnd.randint(0, min(gold, pred)))
        p, r = c.precision, c.recall
        expected = 0.0 if p + r == 0 else 2 * p * r / (p + r)
        assert c.f1 == pytest.approx(expected)


def test_all_has_a_bootstrap_interval_built_from_whole_records():
    """Review finding: ALL used to be None because records contain only entity types."""
    docs = [score_document([M(E, 0, 5), M(P, 6, 9)], [M(E, 0, 5)] if i % 3 else [M(E, 0, 5), M(P, 6, 9)]) for i in range(40)]
    ci = bootstrap_ci(docs, ALL, lambda c: c.recall, seed=4)
    point = aggregate(docs)[ALL].recall
    assert ci is not None and ci[0] <= point <= ci[1]
    # Perfect records give a degenerate but DEFINED interval.
    perfect = [score_document([M(E, 0, 5)], [M(E, 0, 5)]) for _ in range(30)]
    assert bootstrap_ci(perfect, ALL, lambda c: c.recall, 100) == (1.0, 1.0)


def test_all_interval_matches_the_single_type_interval_when_only_one_type_exists():
    docs = [score_document([M(E, 0, 5)], [M(E, 0, 5)] if i % 4 else []) for i in range(30)]
    assert bootstrap_ci(docs, ALL, lambda c: c.recall, seed=9) == bootstrap_ci(docs, E, lambda c: c.recall, seed=9)


def test_aggregate_sums_per_type_and_micro_averages_all():
    docs = [
        score_document([M(E, 0, 5), M(P, 6, 9)], [M(E, 0, 5)]),
        score_document([M(E, 0, 4)], [M(E, 0, 4), M(E, 10, 12)]),
    ]
    totals = aggregate(docs)
    assert totals[E].gold == 2 and totals[E].pred == 3 and totals[E].exact_tp == 2
    assert totals[P].gold == 1 and totals[P].recall == 0
    assert totals[ALL].gold == 3 and totals[ALL].pred == 3 and totals[ALL].exact_tp == 2


def test_bootstrap_interval_is_deterministic_brackets_the_estimate_and_narrows_with_more_data():
    small = [score_document([M(E, 0, 5)], [M(E, 0, 5)] if i % 4 else []) for i in range(20)]
    large = small * 10
    lo_s, hi_s = bootstrap_ci(small, E, lambda c: c.recall, seed=3)
    lo_l, hi_l = bootstrap_ci(large, E, lambda c: c.recall, seed=3)
    assert bootstrap_ci(small, E, lambda c: c.recall, seed=3) == (lo_s, hi_s)  # same seed, same answer
    point = aggregate(small)[E].recall
    assert lo_s <= point <= hi_s and (hi_l - lo_l) < (hi_s - lo_s)


def test_bootstrap_returns_none_when_the_metric_is_never_defined():
    docs = [score_document([], []) for _ in range(5)]
    assert bootstrap_ci(docs, E, lambda c: c.recall) is None
    assert bootstrap_ci([], E, lambda c: c.recall) is None


def test_false_positive_rate_per_thousand_characters():
    rate = FalsePositiveRate()
    rate.add("x" * 600, [M(E, 0, 3), M(P, 5, 9)])
    rate.add("y" * 400, [])
    assert rate.per_1000_chars == pytest.approx(2.0)
    assert rate.records == 2 and rate.records_with_findings == 1 and dict(rate.by_type) == {E: 1, P: 1}
    assert FalsePositiveRate().per_1000_chars is None
