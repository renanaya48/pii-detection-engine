"""Parse the hand-written prompt files into labelled records.

Entries are separated by a line containing only ``---``; lines starting with ``##`` are comments. Inside an entry,
``[[Name]]`` marks a PERSON and ``[[EMAIL:x]]``, ``[[PHONE:x]]``, ``[[CREDIT_CARD:x]]`` mark other PII. The markers are
removed; gold offsets (code points) refer to the resulting text. Titles stay outside the markers, so the labelled span is
the name itself, as in the rest of the evaluation.
"""
from __future__ import annotations

import re

MARKER = re.compile(r"\[\[(?:(PERSON|EMAIL|PHONE|CREDIT_CARD):)?(.+?)\]\]", re.DOTALL)
TITLES = {"dr", "mr", "mrs", "ms", "miss", "prof", "professor", "judge", "inspector", "sir", "madam", "uncle", "aunt",
          "chief", "justice", "captain", "officer", "president", "senator", "father", "sister", "brother"}


def split_entries(text: str) -> list[str]:
    entries, current = [], []
    for line in text.splitlines():
        if line.startswith("##"):
            continue
        if line.strip() == "---":
            entries.append("\n".join(current).strip())
            current = []
        else:
            current.append(line)
    entries.append("\n".join(current).strip())
    return [e for e in entries if e]


def parse_prompt(raw: str) -> tuple[str, list[dict]]:
    """Return the plain text and its gold spans."""
    parts: list[str] = []
    gold: list[dict] = []
    position = length = 0
    for match in MARKER.finditer(raw):
        before = raw[position : match.start()]
        parts.append(before)
        length += len(before)
        entity_type, surface = match.group(1) or "PERSON", match.group(2)
        _validate(entity_type, surface, raw)
        gold.append({"type": entity_type, "start": length, "end": length + len(surface)})
        parts.append(surface)
        length += len(surface)
        position = match.end()
    parts.append(raw[position:])
    text = "".join(parts)
    if "[[" in text or "]]" in text:
        raise ValueError(f"unbalanced or nested markers in: {raw[:60]!r}")
    return text, gold


def _validate(entity_type: str, surface: str, raw: str) -> None:
    if surface != surface.strip() or not surface:
        raise ValueError(f"marker content has surrounding whitespace or is empty in: {raw[:60]!r}")
    if entity_type == "PERSON" and surface.split()[0].rstrip(".").lower() in TITLES:
        raise ValueError(f"titles belong outside the markers ({surface!r}) in: {raw[:60]!r}")


def to_records(text: str, source: str) -> list[dict]:
    """Records for one source file. ``group`` separates prompts with names, with other PII only, and with no PII."""
    records = []
    for i, raw in enumerate(split_entries(text), start=1):
        plain, gold = parse_prompt(raw)
        kinds = {g["type"] for g in gold}
        group = f"names_{source}" if "PERSON" in kinds else f"other_pii_{source}" if kinds else f"negative_{source}"
        records.append({"id": f"prompts-{source}-{i:03d}", "source": f"prompts-{source}", "group": group, "text": plain,
                        "gold": gold, "region": None, "expected_status": None})
    return records
