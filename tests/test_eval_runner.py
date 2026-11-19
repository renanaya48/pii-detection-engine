"""Scoring scope, summaries and reports, with a tiny stub engine (no model needed)."""
from pii_engine.engine import Engine
from pii_engine.types import EntityType as T
from pii_engine.types import Evidence as E
from pii_engine.types import Span

from evaluation.runner import Variant, evaluate, run_set, summarise_types


class _Finds:
    """Recognizer returning fixed spans, so the expected scores are known by construction."""

    name = "stub"

    def __init__(self, *spans):
        self._spans = list(spans)

    def analyze(self, text, ctx=None):
        return self._spans


def variant(*spans):
    return Variant("stub", Engine([_Finds(*spans)]), "strict")


NAME_AND_EMAIL = [Span(T.PERSON, 0, 5, E.MODEL), Span(T.EMAIL, 10, 20, E.PATTERN)]
RECORDS = [{"id": "r1", "text": "Emily and a@b.com123456", "gold": [{"type": "PERSON", "start": 0, "end": 5}]}]


def test_unlabelled_types_do_not_count_as_false_positives_when_scope_is_person():
    """Review finding: WNUT labels only PERSON; a correct name plus an unlabelled email scored precision 50%."""
    outcomes = evaluate(variant(*NAME_AND_EMAIL), RECORDS, scope=("PERSON",))
    summary = summarise_types(outcomes, iterations=10, types=("PERSON",))
    assert summary["PERSON"]["precision"] == 1.0 and summary["PERSON"]["recall"] == 1.0
    assert "ALL" not in summary  # with one scored type, ALL would only repeat it


def test_out_of_scope_findings_are_counted_not_hidden():
    outcomes = evaluate(variant(*NAME_AND_EMAIL), RECORDS, scope=("PERSON",))
    assert outcomes[0].out_of_scope == {"EMAIL": 1} and [m.type for m in outcomes[0].predicted] == ["PERSON"]
    result = run_set("wnut", RECORDS, [variant(*NAME_AND_EMAIL)], iterations=10, groups=False, scope=("PERSON",))
    assert result["variants"]["stub"]["out_of_scope_findings"] == {"EMAIL": 1} and result["scope"] == ["PERSON"]


def test_without_a_scope_every_type_is_scored_and_unlabelled_findings_are_false_positives():
    outcomes = evaluate(variant(*NAME_AND_EMAIL), RECORDS, scope=None)
    summary = summarise_types(outcomes, iterations=10)
    assert summary["ALL"]["precision"] == 0.5 and summary["EMAIL"]["precision"] == 0.0


def test_a_system_that_finds_nothing_scores_zero_recall_and_zero_f1_not_n_a():
    """Review finding, end to end: patterns-only on PERSON must read 0, not 'n/a'."""
    summary = summarise_types(evaluate(variant(), RECORDS, scope=("PERSON",)), iterations=10, types=("PERSON",))
    assert summary["PERSON"]["recall"] == 0 and summary["PERSON"]["f1"] == 0 and summary["PERSON"]["precision"] is None


def test_all_gets_a_confidence_interval_in_the_summary():
    records = [{"id": f"r{i}", "text": "Emily and a@b.com123456", "gold": [{"type": "PERSON", "start": 0, "end": 5}]} for i in range(30)]
    summary = summarise_types(evaluate(variant(*NAME_AND_EMAIL), records, scope=None), iterations=50)
    assert summary["ALL"]["ci95"]["recall"] is not None and summary["PERSON"]["ci95"]["recall"] is not None
