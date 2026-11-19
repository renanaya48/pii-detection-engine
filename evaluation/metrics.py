"""Span-level detection metrics, with the definitions stated so the numbers mean one thing.

Per entity type (a prediction only ever matches a gold span of the SAME type, except where a metric
says "any type"):

* exact precision / recall / F1: a prediction is correct only if type, start and end all equal a gold span.
* coverage recall: a gold span counts as found if same-type predictions TOGETHER cover every one of its
  characters. Leak-oriented: an oversized span is harmless for exposure, a span one digit short is not.
* overlap precision: a prediction counts as correct if it is paired with a gold span of its type, ONE-TO-ONE
  (exact pairs first, then by largest overlap), so several predictions overlapping one name are not all
  counted as hits. Lenient about boundaries.
* any-type coverage recall: a gold span is covered by predictions of ANY type. Separate metric: it answers
  "was this text hidden at all" even when the label is wrong.
* over-marking: characters predicted outside every same-type gold span, as a share of all predicted
  characters (``excess_rate``) and predicted chars relative to gold chars (``over_marking``). Coverage recall
  alone rewards an engine that marks everything; this is the counterweight, because needless redaction is a
  cost (blocked requests, damaged content).

Ratios with an empty denominator are ``None`` (not 0), so "no gold examples" is never reported as "0% recall".
Confidence intervals come from a bootstrap over RECORDS (the unit of resampling), fixed seed.
"""
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

ALL = "ALL"  # micro-average over every entity type

Interval = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Mention:
    type: str
    start: int
    end: int


@dataclass(slots=True)
class Counts:
    gold: int = 0  # gold spans
    pred: int = 0  # predicted spans
    exact_tp: int = 0  # predictions equal to a gold span
    covered: int = 0  # gold spans fully covered by same-type predictions
    covered_any_type: int = 0  # gold spans fully covered by predictions of any type
    overlap_pred: int = 0  # predictions paired one-to-one with a same-type gold span
    gold_chars: int = 0  # characters inside gold spans (union)
    pred_chars: int = 0  # characters inside predicted spans (union)
    excess_chars: int = 0  # predicted characters outside every same-type gold span

    def __add__(self, other: Counts) -> Counts:
        return Counts(*(getattr(self, f) + getattr(other, f) for f in self.__slots__))

    @property
    def precision(self) -> float | None:
        return _ratio(self.exact_tp, self.pred)

    @property
    def recall(self) -> float | None:
        return _ratio(self.exact_tp, self.gold)

    @property
    def f1(self) -> float | None:
        """2*TP / (predictions + gold): the same as the harmonic mean of precision and recall where both
        exist, but still defined (as 0) when every gold entity was missed and nothing was predicted. Only
        "no predictions AND no gold" is undefined."""
        return _ratio(2 * self.exact_tp, self.pred + self.gold)

    @property
    def coverage_recall(self) -> float | None:
        return _ratio(self.covered, self.gold)

    @property
    def coverage_recall_any_type(self) -> float | None:
        return _ratio(self.covered_any_type, self.gold)

    @property
    def overlap_precision(self) -> float | None:
        return _ratio(self.overlap_pred, self.pred)

    @property
    def excess_rate(self) -> float | None:
        """Share of predicted characters that lie outside the gold spans."""
        return _ratio(self.excess_chars, self.pred_chars)

    @property
    def over_marking(self) -> float | None:
        """Predicted characters per gold character (1.0 = same amount; large = marking far too much)."""
        return _ratio(self.pred_chars, self.gold_chars)

    @property
    def false_positives(self) -> int:
        return self.pred - self.exact_tp

    @property
    def false_negatives(self) -> int:
        return self.gold - self.exact_tp


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _union(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _length(intervals: Iterable[Interval]) -> int:
    return sum(end - start for start, end in intervals)


def _intersection_length(a: list[Interval], b: list[Interval]) -> int:
    """Total length shared by two interval unions (both sorted and disjoint)."""
    i = j = total = 0
    while i < len(a) and j < len(b):
        low, high = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        total += max(0, high - low)
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _covers(union: list[Interval], span: Interval) -> bool:
    start, end = span
    return any(low <= start and end <= high for low, high in union)  # unions are merged, so one block must hold it


def _overlap(a: Mention, b: Mention) -> int:
    return max(0, min(a.end, b.end) - max(a.start, b.start))


def _one_to_one(gold: Sequence[Mention], predicted: Sequence[Mention]) -> int:
    """Number of predictions paired with a distinct gold span: exact pairs first, then largest overlap."""
    used_gold: set[int] = set()
    used_pred: set[int] = set()
    for pi, p in enumerate(predicted):  # pass 1: exact matches always win
        for gi, g in enumerate(gold):
            if gi not in used_gold and p == g:
                used_gold.add(gi)
                used_pred.add(pi)
                break
    pairs = sorted(
        ((_overlap(p, g), pi, gi) for pi, p in enumerate(predicted) for gi, g in enumerate(gold)
         if pi not in used_pred and gi not in used_gold and _overlap(p, g) > 0),
        key=lambda t: (-t[0], t[1], t[2]),
    )
    for _, pi, gi in pairs:  # pass 2: greedy by overlap size
        if pi not in used_pred and gi not in used_gold:
            used_pred.add(pi)
            used_gold.add(gi)
    return len(used_pred)


def score_document(gold: Sequence[Mention], predicted: Sequence[Mention]) -> dict[str, Counts]:
    """Per-type counts for one record."""
    any_type_union = _union((p.start, p.end) for p in predicted)
    result: dict[str, Counts] = {}
    for entity_type in {m.type for m in gold} | {m.type for m in predicted}:
        g = [m for m in gold if m.type == entity_type]
        p = [m for m in predicted if m.type == entity_type]
        gold_union = _union((m.start, m.end) for m in g)
        pred_union = _union((m.start, m.end) for m in p)
        result[entity_type] = Counts(
            gold=len(g),
            pred=len(p),
            exact_tp=len(set(p) & set(g)),
            covered=sum(_covers(pred_union, (m.start, m.end)) for m in g),
            covered_any_type=sum(_covers(any_type_union, (m.start, m.end)) for m in g),
            overlap_pred=_one_to_one(g, p),
            gold_chars=_length(gold_union),
            pred_chars=_length(pred_union),
            excess_chars=_length(pred_union) - _intersection_length(pred_union, gold_union),
        )
    return result


def aggregate(per_record: Iterable[Mapping[str, Counts]]) -> dict[str, Counts]:
    """Sum per-record counts into per-type totals plus an ``ALL`` micro-average."""
    totals: dict[str, Counts] = defaultdict(Counts)
    for record in per_record:
        for entity_type, counts in record.items():
            totals[entity_type] = totals[entity_type] + counts
    totals[ALL] = sum((c for t, c in totals.items() if t != ALL), Counts())
    return dict(totals)


Metric = Callable[[Counts], float | None]


def _record_counts(record: Mapping[str, Counts], entity_type: str) -> Counts | None:
    if entity_type == ALL:
        return sum((c for t, c in record.items() if t != ALL), Counts()) if record else None
    return record.get(entity_type)


def bootstrap_cis(
    per_record: Sequence[Mapping[str, Counts]],
    entity_type: str,
    metrics: Mapping[str, Metric],
    iterations: int = 1_000,
    seed: int = 0,
    level: float = 0.95,
) -> dict[str, tuple[float, float] | None]:
    """Percentile bootstrap intervals, one resample per iteration shared by all ``metrics`` (so they are
    consistent with each other). A metric that is never defined on any resample maps to ``None``."""
    rnd = random.Random(seed)
    n = len(per_record)
    samples: dict[str, list[float]] = {name: [] for name in metrics}
    # Per-record counts for the requested type. ``ALL`` is not a key in the records, so it is summed
    # over every type in each record BEFORE resampling (resampling records, not entity types).
    counts_per_record = [_record_counts(record, entity_type) for record in per_record]
    if n:
        for _ in range(iterations):
            total = Counts()
            for _ in range(n):
                counts = counts_per_record[rnd.randrange(n)]
                if counts is not None:
                    total = total + counts
            for name, metric in metrics.items():
                value = metric(total)
                if value is not None:
                    samples[name].append(value)
    result: dict[str, tuple[float, float] | None] = {}
    for name, values in samples.items():
        if not values:
            result[name] = None
            continue
        values.sort()
        low = values[int(((1 - level) / 2) * len(values))]
        high = values[min(int((1 - (1 - level) / 2) * len(values)), len(values) - 1)]
        result[name] = (low, high)
    return result


def bootstrap_ci(
    per_record: Sequence[Mapping[str, Counts]],
    entity_type: str,
    metric: Metric,
    iterations: int = 1_000,
    seed: int = 0,
    level: float = 0.95,
) -> tuple[float, float] | None:
    """Single-metric convenience wrapper around ``bootstrap_cis``."""
    return bootstrap_cis(per_record, entity_type, {"m": metric}, iterations, seed, level)["m"]


@dataclass(slots=True)
class FalsePositiveRate:
    """False positives per 1,000 characters on text that contains no PII."""

    chars: int = 0
    findings: int = 0
    records: int = 0
    records_with_findings: int = 0
    by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, text: str, predicted: Sequence[Mention]) -> None:
        self.chars += len(text)
        self.records += 1
        self.findings += len(predicted)
        self.records_with_findings += bool(predicted)
        for p in predicted:
            self.by_type[p.type] += 1

    @property
    def per_1000_chars(self) -> float | None:
        return self.findings * 1000 / self.chars if self.chars else None
