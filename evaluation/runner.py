"""Run engine variants over evaluation records and summarise the results with evaluation.metrics.

Variants (all share ONE loaded spaCy model, so comparing them costs no extra memory or load time):
  full-balanced / full-strict   the shipped engine, both profiles
  patterns-only                 no NER: shows what the pattern layer alone achieves (PERSON is never found)
  ner-only                      NER only: shows what the model alone achieves on the structured entities (none)
  balanced-two-word-rule        balanced plus the former default rule "a PERSON needs two words": keeps the
                                measured cost of that rule visible after it was removed from the default
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from pii_engine.config import BALANCED, PROFILES, Limits
from pii_engine.engine import Engine
from pii_engine.recognizers import (
    CreditCardRecognizer,
    EmailRecognizer,
    PhoneRecognizer,
    SpacyPersonRecognizer,
    load_model,
)

from .metrics import ALL, Counts, FalsePositiveRate, Mention, aggregate, bootstrap_cis, score_document

TYPES = ("PERSON", "EMAIL", "PHONE", "CREDIT_CARD")
CI_METRICS = {
    "precision": lambda c: c.precision,
    "recall": lambda c: c.recall,
    "f1": lambda c: c.f1,
    "coverage_recall": lambda c: c.coverage_recall,
}
MAX_ERROR_EXAMPLES = 12


@dataclass(frozen=True)
class Variant:
    name: str
    engine: Engine
    profile: str


def build_variants() -> list[Variant]:
    limits = Limits()
    patterns = [EmailRecognizer(limits.regex_timeout_s), CreditCardRecognizer(limits.regex_timeout_s), PhoneRecognizer()]
    ner = SpacyPersonRecognizer(load_model("en"))  # one model, shared
    two_word = replace(BALANCED, name="balanced-two-word-rule", person_min_words=2)
    profiles = {**PROFILES, two_word.name: two_word}
    full = Engine([*patterns, ner], limits, profiles=profiles)
    return [
        Variant("full-balanced", full, "balanced"),
        Variant("full-strict", full, "strict"),
        Variant("balanced-two-word-rule", full, "balanced-two-word-rule"),
        Variant("patterns-only", Engine(patterns, limits, profiles=profiles), "balanced"),
        Variant("ner-only", Engine([ner], limits, profiles=profiles), "balanced"),
    ]


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@dataclass
class Outcome:
    record: dict
    gold: list[Mention]
    predicted: list[Mention]  # in scope only: these are what is scored
    status: str
    out_of_scope: Counter = field(default_factory=Counter)  # findings of types the data set does not label


def evaluate(variant: Variant, records: Sequence[dict], scope: Collection[str] | None = None) -> list[Outcome]:
    """Run the engine over ``records``. ``scope`` limits SCORING to the entity types the data set labels.

    WNUT-17 labels only PERSON. An email the engine finds in such text is not a false alarm (nobody labelled
    emails there), so it must not be scored against the engine; it is counted separately instead.
    """
    outcomes = []
    for record in records:
        result = variant.engine.scan(record["text"], region=record.get("region"), profile=variant.profile)
        everything = [Mention(s.type.value, s.start, s.end) for s in result.spans]
        predicted = [m for m in everything if scope is None or m.type in scope]
        gold = [Mention(g["type"], g["start"], g["end"]) for g in record["gold"]]
        outcomes.append(Outcome(record, gold, predicted, result.status.value, Counter(m.type for m in everything if m not in predicted)))
    return outcomes


def _metrics(counts: Counts) -> dict:
    return {
        "gold": counts.gold, "pred": counts.pred, "exact_tp": counts.exact_tp,
        "precision": counts.precision, "recall": counts.recall, "f1": counts.f1,
        "coverage_recall": counts.coverage_recall, "coverage_recall_any_type": counts.coverage_recall_any_type,
        "overlap_precision": counts.overlap_precision, "excess_rate": counts.excess_rate,
        "over_marking": counts.over_marking, "false_positives": counts.false_positives,
        "false_negatives": counts.false_negatives,
    }


def summarise_types(outcomes: Iterable[Outcome], iterations: int, types: Sequence[str] = TYPES, with_ci: bool = True) -> dict:
    per_record = [score_document(o.gold, o.predicted) for o in outcomes]
    totals = aggregate(per_record)
    summary = {}
    for entity_type in (*types, ALL) if len(types) > 1 else types:  # ALL would just repeat a single type
        counts = totals.get(entity_type, Counts())
        entry = _metrics(counts)
        if with_ci and (counts.gold or counts.pred):
            entry["ci95"] = {k: v for k, v in bootstrap_cis(per_record, entity_type, CI_METRICS, iterations).items()}
        summary[entity_type] = entry
    return summary


def summarise_groups(outcomes: Sequence[Outcome]) -> dict:
    by_group: dict[str, list[Outcome]] = defaultdict(list)
    for o in outcomes:
        by_group[o.record["group"]].append(o)
    groups = {}
    for group, items in by_group.items():
        totals = aggregate(score_document(o.gold, o.predicted) for o in items)
        status = Counter(o.status for o in items)
        expected = items[0].record.get("expected_status")  # one value per group
        entry = {
            "records": len(items),
            "status": dict(status),
            "types": {t: _metrics(c) for t, c in totals.items() if t != ALL},
            "all": _metrics(totals.get(ALL, Counts())),
        }
        if group.startswith("negative"):
            rate = FalsePositiveRate()
            for o in items:
                rate.add(o.record["text"], o.predicted)
            entry["false_positives"] = {
                "per_1000_chars": rate.per_1000_chars, "findings": rate.findings, "records_with_findings": rate.records_with_findings,
                "by_type": dict(rate.by_type),
            }
        if expected:
            entry["expected_status"] = expected
            entry["status_mismatches"] = sum(1 for o in items if o.status != expected)
        groups[group] = entry
    return groups


def _snippet(text: str, start: int, end: int, width: int = 35) -> str:
    return text[max(0, start - width) : start] + "[[" + text[start:end] + "]]" + text[end : end + width]


def collect_errors(outcomes: Iterable[Outcome]) -> dict:
    """A capped sample of misses and false alarms, for error analysis (not for scoring)."""
    misses, false_alarms = [], []
    for o in outcomes:
        gold, predicted = set(o.gold), set(o.predicted)
        for g in o.gold:
            if g not in predicted and len(misses) < MAX_ERROR_EXAMPLES * 4:
                misses.append({"id": o.record["id"], "group": o.record.get("group"), "type": g.type, "text": _snippet(o.record["text"], g.start, g.end)})
        for p in o.predicted:
            if p not in gold and len(false_alarms) < MAX_ERROR_EXAMPLES * 4:
                false_alarms.append({"id": o.record["id"], "group": o.record.get("group"), "type": p.type, "text": _snippet(o.record["text"], p.start, p.end)})
    return {"false_negatives": misses, "false_positives": false_alarms}


def run_set(
    name: str, records: Sequence[dict], variants: Sequence[Variant], iterations: int, groups: bool,
    scope: Sequence[str] | None = None,
) -> dict:
    result: dict = {"records": len(records), "scope": list(scope or TYPES), "variants": {}}
    errors: dict = {}
    for variant in variants:
        outcomes = evaluate(variant, records, scope)
        entry = {"types": summarise_types(outcomes, iterations, tuple(scope or TYPES)),
                 "status": dict(Counter(o.status for o in outcomes))}
        if scope:
            entry["out_of_scope_findings"] = dict(sum((o.out_of_scope for o in outcomes), Counter()))
        if groups:
            entry["groups"] = summarise_groups(outcomes)
        result["variants"][variant.name] = entry
        errors[variant.name] = collect_errors(outcomes)
    result["errors"] = errors
    return result
