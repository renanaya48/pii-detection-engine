"""Command line: ``python -m pii_engine [TEXT | --file PATH | -] [--region XX] [--profile strict|balanced]``.

Prints only the public contract as JSON: ``{"status": ..., "results": [{"type", "start", "end"}]}``.
Never prints the input or matched text. Exit code: 0 scan ran (complete or partial), 1 status failed,
2 usage or input error.

Single core: this process uses one thread for its own code; the numeric libraries are told to use one
thread before they are imported. To pin the process to one CPU as well, use the OS (Windows:
``start /affinity 1 python -m pii_engine ...``; Linux: ``taskset -c 0 python -m pii_engine ...``).
"""
from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import argparse
import json
import sys
from collections.abc import Callable, Sequence

from .config import DEFAULT_PROFILE, PROFILES
from .engine import Engine, default_engine
from .types import ScanStatus


def _read_input(args: argparse.Namespace, limit: int) -> str:
    """Read at most ``limit`` + 1 characters, so an oversized input is detected without loading all of it."""
    if args.file is not None:
        with open(args.file, encoding="utf-8") as handle:  # path comes from the operator's argv, never from the text
            return handle.read(limit + 1)
    if args.text is not None and args.text != "-":
        return args.text
    return sys.stdin.read(limit + 1)


def main(argv: Sequence[str] | None = None, engine_factory: Callable[[], Engine] = default_engine) -> int:
    parser = argparse.ArgumentParser(prog="pii_engine", description="Detect PII entities in text.")
    parser.add_argument("text", nargs="?", help="text to scan; omit or use '-' to read stdin")
    parser.add_argument("--file", help="read the text from a UTF-8 file")
    parser.add_argument("--region", help="ISO 3166 alpha-2 code (e.g. US) to enable local phone formats")
    parser.add_argument("--profile", choices=sorted(PROFILES), default=DEFAULT_PROFILE)
    args = parser.parse_args(argv)
    if args.file is not None and args.text is not None:
        parser.error("give either TEXT or --file, not both")

    # Read with the ENGINE's limit (plus one character, so oversized input is seen and reported as
    # FAILED instead of being silently cut to a prefix). A separate copy of the limit could drift.
    engine = engine_factory()
    try:
        text = _read_input(args, engine.max_chars)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"error: cannot read input ({type(exc).__name__})", file=sys.stderr)  # class only, never content
        return 2

    result = engine.scan(text, region=args.region, profile=args.profile)
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 1 if result.status is ScanStatus.FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
