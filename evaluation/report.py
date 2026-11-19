"""Render the JSON results as markdown tables (generated, never edited by hand)."""
from __future__ import annotations

TYPES = ("PERSON", "EMAIL", "PHONE", "CREDIT_CARD")


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.1f}"


def with_ci(entry: dict, key: str) -> str:
    value = entry.get(key)
    interval = (entry.get("ci95") or {}).get(key)
    if value is None:
        return "n/a"
    return f"{pct(value)} [{pct(interval[0])}–{pct(interval[1])}]" if interval else pct(value)


def _table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def headline(set_result: dict, entity_types: tuple[str, ...]) -> str:
    rows = []
    for variant, data in set_result["variants"].items():
        for entity_type in entity_types:
            t = data["types"][entity_type]
            if not (t["gold"] or t["pred"]):
                continue
            rows.append([variant, entity_type, str(t["gold"]), str(t["pred"]), with_ci(t, "precision"), with_ci(t, "recall"),
                         with_ci(t, "f1"), with_ci(t, "coverage_recall"), pct(t["coverage_recall_any_type"]),
                         pct(t["overlap_precision"]), pct(t["excess_rate"])])
    return _table(["variant", "type", "gold", "pred", "precision %", "recall %", "F1 %", "coverage recall %", "any-type coverage %",
                   "overlap precision %", "excess chars %"], rows)


def groups_table(set_result: dict, variant: str) -> str:
    rows = []
    for group, g in set_result["variants"][variant]["groups"].items():
        a = g["all"]
        status = ", ".join(f"{k} {v}" for k, v in sorted(g["status"].items()))
        fp = g.get("false_positives")
        rows.append([group, str(g["records"]), str(a["gold"]), str(a["pred"]), pct(a["recall"]), pct(a["coverage_recall"]),
                     pct(a["precision"]), pct(a["excess_rate"]),
                     f"{fp['per_1000_chars']:.2f}" if fp and fp["per_1000_chars"] is not None else "–", status])
    return _table(["group", "records", "gold", "pred", "recall %", "coverage %", "precision %", "excess %", "FP / 1k chars", "status"], rows)


def markdown(report: dict) -> str:
    meta = report["meta"]
    out = [f"# Evaluation results: {meta['split']} split",
           f"engine source `{meta['code_hash']}`, data `{meta['data_hash']}`, {meta['timestamp']}, "
           f"python {meta['python']}, spaCy {meta['spacy']}, phonenumbers {meta['phonenumbers']}, "
           f"bootstrap {meta['bootstrap_iterations']} resamples over records (95% intervals in brackets).", ""]
    sets = report["sets"]
    wnut = sets["wnut17"]
    skipped = {v: d.get("out_of_scope_findings", {}) for v, d in wnut["variants"].items()}
    out += ["## WNUT-17 (real informal text; labels PERSON only, so only PERSON is scored)", headline(wnut, ("PERSON",)),
            "Findings of other types are not scored (the corpus does not label them): "
            + ", ".join(f"{v}: {sum(c.values())}" for v, c in skipped.items()), ""]
    out += ["## Synthetic: all entity types", headline(sets["synthetic"], (*TYPES, "ALL")), ""]
    for variant in ("full-balanced", "full-strict"):
        out += [f"## Synthetic by group: {variant}", groups_table(sets["synthetic"], variant), ""]
    return "\n".join(out)
