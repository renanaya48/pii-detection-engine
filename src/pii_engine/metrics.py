"""Aggregate-only metrics.

Deliberately has no API that accepts text, offsets or evidence: counters and
latency sums only, so nothing sensitive can end up in logs by accident.
"""
from __future__ import annotations

from collections import Counter


class Metrics:
    def __init__(self) -> None:
        self.scans = 0
        self.latency_ms_total = 0.0
        self.status: Counter[str] = Counter()
        self.entities: Counter[str] = Counter()
        self.recognizer_errors: Counter[str] = Counter()
        self.recognizer_skips: Counter[str] = Counter()

    def record_scan(self, latency_ms: float, status: str, entity_types: list[str]) -> None:
        self.scans += 1
        self.latency_ms_total += latency_ms
        self.status[status] += 1
        self.entities.update(entity_types)

    def record_error(self, recognizer: str, error_kind: str) -> None:
        # error_kind is an exception class name, never its message (messages may echo input).
        self.recognizer_errors[f"{recognizer}:{error_kind}"] += 1

    def record_skip(self, recognizer: str, reason: str) -> None:
        self.recognizer_skips[f"{recognizer}:{reason}"] += 1

    def snapshot(self) -> dict:
        return {
            "scans": self.scans,
            "mean_latency_ms": self.latency_ms_total / self.scans if self.scans else 0.0,
            "status": dict(self.status),
            "entities": dict(self.entities),
            "recognizer_errors": dict(self.recognizer_errors),
            "recognizer_skips": dict(self.recognizer_skips),
        }
