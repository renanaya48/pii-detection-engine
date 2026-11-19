"""Whole-request latency and peak memory for long input, per segment size.

Usage (repo root, `pii` env):
    python bench/long_input.py              # compares several segment sizes, one fresh process each
    python bench/long_input.py child 4000   # internal: one segment size

Measures the full request (all segments, overlaps included), pinned to one core.
"""
import os
import subprocess
import sys

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import statistics
import time

from _env import memory_mib as mem, pin_to_one_core

SIZES = (5_000, 20_000, 50_000, 100_000)
RUNS = 5
BASE = (
    "Yesterday Emily Carter called Michael Johnson about the contract, please send it to "
    "emily.carter@example.com or call +44 20 7946 0958 before Friday. "
) * 1000


def child(segment_chars: int) -> None:
    print(pin_to_one_core())
    from pii_engine.config import Limits
    from pii_engine.engine import default_engine

    limits = Limits(max_chars=200_000, segment_chars=segment_chars, segment_overlap=min(200, segment_chars // 4))
    engine = default_engine(limits)
    print(f"segment_chars={segment_chars}: after load current/peak MiB = {mem()}")
    print("  chars | findings | status   | mean ms | min ms | max ms | mem current/peak MiB")
    for n in SIZES:
        text = BASE[:n]
        engine.scan(text)  # warm
        times = []
        for _ in range(RUNS):
            t0 = time.perf_counter()
            result = engine.scan(text)
            times.append((time.perf_counter() - t0) * 1000)
        print(
            f"  {n:>6} | {len(result.spans):8} | {result.status.value:8} | {statistics.fmean(times):7.0f} | "
            f"{min(times):6.0f} | {max(times):6.0f} | {mem()}"
        )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "child":
        child(int(sys.argv[2]))
    else:
        for size in (2_000, 4_000, 8_000):
            subprocess.run([sys.executable, __file__, "child", str(size)], check=True)
