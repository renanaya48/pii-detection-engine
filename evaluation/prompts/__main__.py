"""Build and run the well-cased prompt check.

    python -m evaluation.prompts build              # parse the prompt files, write prompts.jsonl and MANIFEST.json
    python -m evaluation.prompts run --final        # score the frozen engine ONCE; logged, refused on repeat

Rules (also in README.md):
* ``build`` needs the existing freeze to be intact and records its id in the manifest, so the data set is tied to one
  exact engine version. ``build`` is refused once a run has been logged: a set that has been scored is final.
* ``run`` refuses unless the freeze is intact, the data and source hashes match the manifest, and no earlier run is in
  the log (``--again`` overrides, and is logged). The attempt is logged BEFORE scoring and closed as ok or failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evaluation import freeze
from evaluation.report import groups_table, headline

from .parse import to_records

HERE = Path(__file__).parent
SOURCES = {"author": HERE / "author_prompts.txt", "user": HERE / "user_prompts.txt"}
DATA = HERE / "prompts.jsonl"
MANIFEST = HERE / "MANIFEST.json"
LOG = HERE / "prompts_runs.log"
RESULTS = HERE / "results"

COMPOSITION_NOTE = (
    "Purposive sample, NOT representative traffic. Roughly two thirds of the prompts contain names and one third do not; "
    "that ratio was chosen by the authors, so precision and false-alarm figures depend on it. Prompts are correctly cased "
    "by design, which is an assumption about typical input: real prompts are often lowercase and informal (see the WNUT-17 "
    "results). AI-authored prompts from two assistant interactions; 30 were supplied by the project owner (see "
    "PROVENANCE_CORRECTION.md); a few famous names are included."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _names(records: list[dict], source: str) -> set[str]:
    return {r["text"][g["start"] : g["end"]] for r in records if r["source"] == source for g in r["gold"] if g["type"] == "PERSON"}


def _frozen_id() -> str:
    changed = freeze.differences()
    if changed:
        raise SystemExit("the frozen engine state is not intact: " + "; ".join(changed))
    return freeze.freeze_id(json.loads(freeze.FREEZE_FILE.read_text(encoding="utf-8")))


def _log_lines() -> list[str]:
    return LOG.read_text(encoding="utf-8").splitlines() if LOG.exists() else []


def build() -> dict:
    if _log_lines():
        raise SystemExit("this prompt set has already been scored; it is final and cannot be rebuilt")
    frozen = _frozen_id()
    records = []
    for source, path in SOURCES.items():
        records += to_records(path.read_text(encoding="utf-8"), source) if path.exists() else []
    if not records:
        raise SystemExit("no prompts found")
    DATA.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8", newline="\n")
    persons = [g for r in records for g in r["gold"] if g["type"] == "PERSON"]
    manifest = {
        "name": "prompts: purposive, well-cased",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frozen_engine": {"freeze_id": frozen, "engine_source": json.loads(freeze.FREEZE_FILE.read_text(encoding="utf-8"))["components"]["engine_source"]},
        "sources": {name: _sha256(path) for name, path in SOURCES.items() if path.exists()},
        "data": {DATA.name: _sha256(DATA)},
        "counts": {
            "records": len(records),
            "with_person": sum(any(g["type"] == "PERSON" for g in r["gold"]) for r in records),
            "without_person": sum(all(g["type"] != "PERSON" for g in r["gold"]) for r in records),
            "person_mentions": len(persons),
            # WNUT names are mostly one word; these prompts mostly use full names, which is easier. Recorded, not hidden.
            "single_word_person_mentions": sum(
                " " not in r["text"][g["start"] : g["end"]] for r in records for g in r["gold"] if g["type"] == "PERSON"),
            "by_source": {s: sum(r["source"] == f"prompts-{s}" for r in records) for s in SOURCES},
            # independence of the two sources: names that appear in both files
            "person_names_in_both_sources": len(_names(records, "prompts-author") & _names(records, "prompts-user")),
        },
        "composition_note": COMPOSITION_NOTE,
        "status": "built, not yet scored",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def guard_run(final: bool, again: bool) -> dict:
    if not final:
        raise SystemExit("pass --final to score the prompt set (it is logged and can be run once)")
    if not MANIFEST.exists() or not DATA.exists():
        raise SystemExit("no manifest: run `python -m evaluation.prompts build` first")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if _sha256(DATA) != manifest["data"][DATA.name]:
        raise SystemExit("prompts.jsonl changed since the manifest was written")
    for name, path in SOURCES.items():
        if path.exists() and manifest["sources"].get(name) != _sha256(path):
            raise SystemExit(f"{path.name} changed since the manifest was written; rebuild first")
    if manifest["frozen_engine"]["freeze_id"] != _frozen_id():
        raise SystemExit("the manifest was built against a different frozen engine version")
    if _log_lines() and not again:
        raise SystemExit("this prompt set has already been scored once; use --again only for an intentional, logged repeat")
    return manifest


def log_event(manifest: dict, again: bool, status: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} data={manifest['data'][DATA.name][:16]} freeze={manifest['frozen_engine']['freeze_id']} "
                     f"again={again} status={status}\n")


def render(manifest: dict, result: dict) -> str:
    c = manifest["counts"]
    out = ["# Well-cased prompt check (frozen engine, scored once)",
           f"{c['records']} prompts ({c['with_person']} with names, {c['without_person']} without; {c['person_mentions']} name mentions, "
           f"{c['single_word_person_mentions']} of them single words; {c['person_names_in_both_sources']} names occur in both the "
           f"author's and the owner's prompts, so the two sources are not independent); "
           f"data `{manifest['data'][DATA.name][:12]}`, frozen engine `{manifest['frozen_engine']['freeze_id']}`.",
           "", f"> {manifest['composition_note']}", "",
           "## Overall", headline(result, ("PERSON", "EMAIL", "PHONE", "CREDIT_CARD", "ALL")), "",
           "## By group (full-balanced)", groups_table(result, "full-balanced"), "",
           "## By group (full-strict)", groups_table(result, "full-strict"), ""]
    return "\n".join(out)


def run(final: bool, again: bool, iterations: int) -> dict:
    from evaluation.runner import build_variants, load_jsonl, run_set

    manifest = guard_run(final, again)
    log_event(manifest, again, "started")  # before any scoring
    try:
        records = load_jsonl(DATA)
        result = run_set("prompts", records, build_variants(), iterations, groups=True)
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "prompts_final.json").write_text(json.dumps({"manifest": manifest, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
        (RESULTS / "prompts_final.md").write_text(render(manifest, result), encoding="utf-8")
    except BaseException:
        log_event(manifest, again, "failed")
        raise
    log_event(manifest, again, "ok")
    manifest["status"] = "scored"
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.prompts")
    parser.add_argument("command", choices=("build", "run"))
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--again", action="store_true")
    parser.add_argument("--iterations", type=int, default=1_000)
    args = parser.parse_args(argv)
    if args.command == "build":
        manifest = build()
        print(f"built {manifest['counts']['records']} prompts: {manifest['counts']}", file=sys.stderr)
    else:
        run(args.final, args.again, args.iterations)
        print(f"wrote {RESULTS / 'prompts_final.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
