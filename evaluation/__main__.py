"""Command line for the evaluation.

    python -m evaluation --split dev                       # development: run as often as you like
    python -m evaluation --split test --final              # held-out: logged, and refused if repeated on unchanged code

Protocol (also in evaluation/README.md):
* dev is for error analysis and engine changes. Anything tuned after looking at a sample is dev data.
* test is run once per code version. The attempt is appended to evaluation/results/test_runs.log BEFORE any
  test data is scored (status=started) and closed afterwards (status=ok or failed), with hashes of the engine
  source and the data. A second attempt on the SAME source hash is refused, whatever the first one's status,
  unless --again is given; --again is itself logged. A change made after seeing test results means test is no
  longer held out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import freeze
from .report import markdown
from .runner import build_variants, load_jsonl, run_set

ROOT = Path(__file__).parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
SRC = ROOT.parent / "src" / "pii_engine"


@dataclass(frozen=True)
class Dataset:
    pattern: str  # file name with a {split} placeholder
    scope: tuple[str, ...] | None  # entity types the data set labels (None = all four)
    groups: bool  # whether records carry a "group" for per-group tables


SETS = {
    "wnut17": Dataset("wnut17_{split}.jsonl", scope=("PERSON",), groups=False),  # labels PERSON only
    "synthetic": Dataset("synthetic_{split}.jsonl", scope=None, groups=True),
}


def _sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def code_hash() -> str:
    return _sha256(list(SRC.rglob("*.py")))


def data_hash(split: str) -> str:
    return _sha256([DATA / d.pattern.format(split=split) for d in SETS.values()])


def guard_test_split(final: bool, again: bool) -> None:
    log = RESULTS / "test_runs.log"
    if not final:
        raise SystemExit("the test split is held out: pass --final to run it (it is logged)")
    changed = freeze.differences()
    if changed:  # the held-out run must be on the exact frozen engine, evaluation code, data and dependencies
        raise SystemExit("the test split runs only on a frozen state: " + "; ".join(changed))
    previous = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    if any(f"code={code_hash()}" in line for line in previous) and not again:
        raise SystemExit(
            f"test was already evaluated (or attempted) with this exact engine source (code={code_hash()}); "
            "repeating it would make test a tuning set. Use --again only if the repeat is intentional (it is logged)."
        )


def log_test_event(again: bool, status: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "test_runs.log").open("a", encoding="utf-8") as handle:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        frozen = freeze.freeze_id(json.loads(freeze.FREEZE_FILE.read_text(encoding="utf-8"))) if freeze.FREEZE_FILE.exists() else "none"
        handle.write(f"{stamp} code={code_hash()} data={data_hash('test')} freeze={frozen} again={again} status={status}\n")


def evaluate_split(split: str, iterations: int, tag: str) -> dict:
    """Score every data set of ``split``, write the JSON and markdown reports, return the report."""
    import phonenumbers
    import spacy

    variants = build_variants()
    sets = {}
    for name, dataset in SETS.items():
        records = load_jsonl(DATA / dataset.pattern.format(split=split))
        print(f"{name}: {len(records)} records", file=sys.stderr)
        sets[name] = run_set(name, records, variants, iterations, groups=dataset.groups, scope=dataset.scope)
    report = {
        "meta": {
            "split": split, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "code_hash": code_hash(), "data_hash": data_hash(split), "bootstrap_iterations": iterations,
            "python": platform.python_version(), "spacy": spacy.__version__, "phonenumbers": phonenumbers.__version__,
        },
        "sets": sets,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"{split}{('_' + tag) if tag else ''}"
    (RESULTS / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / f"{stem}.md").write_text(markdown(report), encoding="utf-8")
    print(f"wrote {RESULTS / (stem + '.json')} and {stem}.md", file=sys.stderr)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation")
    parser.add_argument("--split", choices=("dev", "test"))
    parser.add_argument("--freeze", action="store_true", help="record the engine, evaluation code, data and dependencies")
    parser.add_argument("--final", action="store_true", help="required to run the held-out test split")
    parser.add_argument("--again", action="store_true", help="repeat the test split on unchanged code (logged)")
    parser.add_argument("--iterations", type=int, default=1_000, help="bootstrap resamples per confidence interval")
    parser.add_argument("--tag", default="", help="suffix for the output file names")
    args = parser.parse_args(argv)
    if args.freeze:
        data = freeze.write_freeze()
        print(f"froze state {freeze.freeze_id(data)}: " + ", ".join(f"{k}={v[:10]}" for k, v in data["components"].items()), file=sys.stderr)
        return 0
    if not args.split:
        parser.error("--split is required (or use --freeze)")

    held_out = args.split == "test"
    if held_out:
        guard_test_split(args.final, args.again)
        log_test_event(args.again, "started")  # recorded BEFORE any test data is scored
    try:
        evaluate_split(args.split, args.iterations, args.tag)
    except BaseException:  # includes KeyboardInterrupt: an interrupted run still used the held-out data
        if held_out:
            log_test_event(args.again, "failed")
        raise
    if held_out:
        log_test_event(args.again, "ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
