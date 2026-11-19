"""Where does the end-of-benchmark memory peak come from? A diagnostic, not a benchmark: it only READS the engine.

Each condition must run in its OWN process (memory is cumulative), pinned to one core, one numeric thread:

    python bench/memory_probe.py --before none           # fresh process, then the repeated scans alone
    python bench/memory_probe.py --before sizes          # after the size sweep up to 10,000 chars
    python bench/memory_probe.py --before big            # after 100,000-char inputs of several shapes
    python bench/memory_probe.py --before full           # after the same phases as bench/final_measure.py
    python bench/memory_probe.py --before none --no-sampling   # no measurement calls between scans
    python bench/memory_probe.py --before none --scans 8000    # does the peak keep rising?

Reports bytes from the OS working-set counters: current working set, peak working set (cumulative) and private bytes.
"""
import argparse
import gc
import os

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import psutil

from _env import pin_to_one_core

LIMIT_BYTES = 150_000_000  # the conservative reading of "150 MB"
MIB = 1024 * 1024


def snapshot() -> dict:
    info = psutil.Process().memory_info()
    return {"rss": info.rss, "peak": getattr(info, "peak_wset", info.rss), "private": getattr(info, "private", 0)}


def fmt(snap: dict) -> str:
    return (f"working set {snap['rss']:>11,} B ({snap['rss'] / MIB:6.1f} MiB) | peak {snap['peak']:>11,} B ({snap['peak'] / MIB:6.1f} MiB) "
            f"| private {snap['private'] / MIB:6.1f} MiB")


def replicate_benchmark(engine, skip: set[str]) -> None:
    """The same phases, texts and scan counts as bench/final_measure.py (one first scan, one warm-up, then the timed runs),
    so a group can be left out to see which one leaves the memory behind."""
    from final_measure import DENSE, HEBREW, SPANISH, repeat_text, runs_for, sparse_text

    def measure_like(text: str, runs: int, **kw) -> None:
        for _ in range(2 + runs):
            engine.scan(text, **kw)

    if "sizes" not in skip:
        for n in (500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000):
            measure_like(sparse_text(n), runs_for(n))
    if "dense" not in skip:
        for n in (1_000, 5_000, 20_000, 100_000):
            measure_like(repeat_text(DENSE, n), runs_for(n))
    if "nonenglish" not in skip:
        measure_like(repeat_text(SPANISH, 5_000), 30)
        measure_like(repeat_text(HEBREW, 5_000), 30)
    if "hostile" not in skip:
        for unit in ("1 2 ", "+1 2 3 4 5 6 7 8 9 ", "a@", "a", "a@b.co ", "4111 1111 1111 1111 ", "+44 20 7946 0958 "):
            measure_like(repeat_text(unit, 100_000), 3)
    if "regions" not in skip:
        text = "call (415) 555-2671, 020 7946 0958, 612 345 678, 030 123456, 01 70 18 99 00, 03-1234-5678, 0412 345 678 now"
        for region in ("US", "GB", "ES", "DE", "FR", "IL", "JP", "IN", "BR", "AU"):
            engine.scan(text, region=region)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", choices=("none", "sizes", "big", "full", "benchmark"), default="none")
    parser.add_argument("--skip", default="", help="with --before benchmark: comma list of groups to leave out "
                        "(sizes, dense, nonenglish, hostile, regions)")
    parser.add_argument("--cpu-model", action="store_true",
                        help="call the helper that starts a PowerShell process to read the CPU name, as bench/final_measure.py does")
    parser.add_argument("--scans", type=int, default=2_000)
    parser.add_argument("--every", type=int, default=250)
    parser.add_argument("--no-sampling", action="store_true", help="read memory only at the start and the end")
    parser.add_argument("--collect", action="store_true", help="gc.collect() before the final reading")
    args = parser.parse_args()

    print(pin_to_one_core())
    from final_measure import DENSE, repeat_text, sparse_text  # reuses the benchmark's own text builders

    from pii_engine.config import Limits
    from pii_engine.engine import default_engine

    print("before engine, before cpu-model call:", fmt(snapshot()))
    if args.cpu_model:
        from _env import cpu_model

        print("cpu model:", cpu_model())
        print("after the cpu-model call:           ", fmt(snapshot()))
    engine = default_engine(Limits(max_chars=100_000))
    print("after engine load:      ", fmt(snapshot()))

    def scan_many(text: str, times: int) -> None:
        for _ in range(times):
            engine.scan(text)

    if args.before in ("sizes", "full"):
        for n in (500, 1_000, 2_000, 5_000, 10_000):
            scan_many(sparse_text(n), 30)
    if args.before == "full":
        for n in (20_000, 50_000, 100_000):
            scan_many(sparse_text(n), 5)
        for n in (1_000, 5_000, 20_000, 100_000):
            scan_many(repeat_text(DENSE, n), 5)
    if args.before in ("big", "full"):
        for unit in (DENSE, "a@b.co ", "4111 1111 1111 1111 ", "+44 20 7946 0958 ", "1 2 "):
            scan_many(repeat_text(unit, 100_000), 3)
    if args.before == "benchmark":
        replicate_benchmark(engine, {s for s in args.skip.split(",") if s})
    print(f"after phase '{args.before}': ", fmt(snapshot()))

    texts = [sparse_text(500), sparse_text(1_000), sparse_text(2_000), sparse_text(5_000)]
    print(f"repeated scans: {args.scans} (cycling 500 / 1,000 / 2,000 / 5,000 chars), sampling {'off' if args.no_sampling else f'every {args.every}'}")
    for i in range(1, args.scans + 1):
        engine.scan(texts[i % len(texts)])
        if not args.no_sampling and i % args.every == 0:
            print(f"  after {i:>5} scans:   ", fmt(snapshot()))
    if args.collect:
        gc.collect()
    end = snapshot()
    verdict = "OVER" if end["peak"] > LIMIT_BYTES else "within"
    print("END:                    ", fmt(end))
    print(f"peak {end['peak']:,} B vs limit {LIMIT_BYTES:,} B ({LIMIT_BYTES / MIB:.2f} MiB): {verdict} by {(end['peak'] - LIMIT_BYTES):+,} B")


if __name__ == "__main__":
    main()
