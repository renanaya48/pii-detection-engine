"""Freeze manifest: ties a held-out result to an exact version of everything that produced it.

``python -m evaluation --freeze`` writes evaluation/FREEZE.json; ``--split test --final`` refuses to run unless
the current state still matches it. The manifest covers the engine source, the evaluation code, every data file,
the pinned dependency list and the NER model version, so a report can be attributed to one precise state.
README text and result files are deliberately NOT part of it (editing documentation must not unfreeze anything).
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT.parent
FREEZE_FILE = ROOT / "FREEZE.json"


def _sha256(paths: list[Path], base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(base).as_posix().encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))  # line endings must not change the hash
    return digest.hexdigest()


def _components() -> dict[str, str]:
    return {
        "engine_source": _sha256(list((REPO / "src" / "pii_engine").rglob("*.py")), REPO),
        "evaluation_code": _sha256(list(ROOT.glob("*.py")), ROOT),
        "evaluation_data": _sha256(list((ROOT / "data").glob("*.jsonl")), ROOT),
        "dependencies": _sha256([REPO / "requirements-tested.txt"], REPO),
    }


def _model_version() -> str:
    import spacy

    return f"en_core_web_sm {spacy.info('en_core_web_sm', silent=True)['version']}, spacy {spacy.__version__}"


def manifest() -> dict:
    return {
        "components": _components(),
        "model": _model_version(),
        "python": platform.python_version(),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def freeze_id(data: dict) -> str:
    """Short id of the frozen state (not of the creation time), recorded in the test log."""
    payload = json.dumps({"components": data["components"], "model": data["model"], "python": data["python"]}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def write_freeze(path: Path | None = None) -> dict:
    path = path or FREEZE_FILE
    data = manifest()
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def differences(path: Path | None = None) -> list[str]:
    """What changed since the freeze, as readable strings; an empty list means the state is frozen and intact."""
    path = path or FREEZE_FILE
    if not path.exists():
        return ["no freeze recorded (run `python -m evaluation --freeze` first)"]
    frozen = json.loads(path.read_text(encoding="utf-8"))
    now = manifest()
    changed = [f"{name} changed since the freeze" for name, value in frozen["components"].items() if now["components"].get(name) != value]
    changed += [f"{key} changed: {frozen[key]!r} -> {now[key]!r}" for key in ("model", "python") if frozen[key] != now[key]]
    return changed
