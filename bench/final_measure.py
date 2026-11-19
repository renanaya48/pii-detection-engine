"""Final whole-engine measurements for Task 2 (also the base for Task 3).

Usage (repo root, `pii` env):   python bench/final_measure.py
Run it several times in separate processes to see run-to-run spread (the machine is noisy).

Everything is measured through the real default engine, in one process pinned to one core, so memory
is whole-process (interpreter + libraries + model + working memory). Sizes are reported as characters
AND UTF-8 bytes: they differ for non-ASCII text.
"""
import os

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import statistics
import sys
import time

from _env import cpu_model, memory_mib as mem, os_name, pin_to_one_core

PLAIN = [
    "The quarterly report was reviewed and the team agreed to move the deadline to next week.",
    "Please make sure the documentation is updated before the release goes out on Friday.",
    "We discussed the budget for the new project and decided to postpone the final decision.",
    "The meeting notes are available in the shared folder for anyone who wants to read them.",
]
WITH_PII = [
    "Please send the invoice to Emily Carter at emily.carter@example.com.",
    "You can reach Michael Johnson on +44 20 7946 0958 if it is urgent.",
    "The card ending in 4111 1111 1111 1111 was declined again.",
]
DENSE = (
    "Yesterday Emily Carter called Michael Johnson about the contract, please send it to "
    "emily.carter@example.com or call +44 20 7946 0958 before Friday. "
)
SPANISH = "Ayer Lucía Fernández llamó a Carlos Martínez para hablar del contrato y de los pagos pendientes. "
HEBREW = "שלום, אני רוצה לשלוח את החשבונית לדוד כהן עד יום שישי בבוקר, תודה רבה לכם. "

# ASSUMED typical request mix (the exercise defines none): mostly short prompts, a long tail.
# Weights are an assumption, stated so a reader can substitute their own.
MIX = {500: 0.40, 1_000: 0.25, 2_000: 0.20, 5_000: 0.10, 10_000: 0.05}


def sparse_text(n: int) -> str:
    """Mostly plain prose with one PII sentence in every five (~1 finding per 400 chars)."""
    parts, size, i = [], 0, 0
    while size < n:
        s = WITH_PII[(i // 5) % len(WITH_PII)] if i % 5 == 4 else PLAIN[i % len(PLAIN)]
        parts.append(s)
        size += len(s) + 1
        i += 1
    return fit(" ".join(parts), n)


def repeat_text(unit: str, n: int) -> str:
    return fit(unit * (n // len(unit) + 1), n)


def fit(text: str, n: int) -> str:
    text = text[:n]
    cut = text.rfind(" ")
    return text if cut < n * 0.9 else text[:cut]


def runs_for(n: int) -> int:
    return 30 if n <= 5_000 else 10 if n <= 20_000 else 5 if n <= 50_000 else 3


def measure(engine, text: str, runs: int, **kw) -> dict:
    t0 = time.perf_counter()
    first_result = engine.scan(text, **kw)
    first = (time.perf_counter() - t0) * 1000
    engine.scan(text, **kw)  # warm
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        engine.scan(text, **kw)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "chars": len(text), "bytes": len(text.encode("utf-8")), "findings": len(first_result.spans),
        "status": first_result.status.value, "first": first, "mean": statistics.fmean(times),
        "median": statistics.median(times), "max": times[-1],
        "p95": times[max(int(0.95 * len(times)) - 1, 0)] if len(times) >= 20 else None,
    }


def row(label: str, m: dict) -> str:
    p95 = f"{m['p95']:7.1f}" if m["p95"] is not None else "      -"
    return (f"{label:<9}| {m['chars']:>7} | {m['bytes']:>7} | {m['findings']:>8} | {m['status']:<8} | {m['first']:8.1f} | "
            f"{m['mean']:8.1f} | {m['median']:8.1f} | {p95} | {m['max']:8.1f}")


HEADER = "text     |   chars |   bytes | findings | status   | first ms | mean ms  | median   | p95 ms  | max ms"


def main() -> None:
    pinned = pin_to_one_core()
    import phonenumbers
    import spacy

    from pii_engine.config import Limits
    from pii_engine.engine import default_engine

    # No platform.system()/uname() here: on Windows + Python 3.12 they load WMI and add ~5 MiB to the measured process.
    print(f"CPU: {cpu_model()} | Python {'.'.join(map(str, sys.version_info[:3]))} | spaCy {spacy.__version__} | "
          f"phonenumbers {phonenumbers.__version__} | {os_name()} | {pinned}, 1 BLAS/OMP thread")
    print(f"Memory before engine (interpreter + imports of this script): current/peak MiB = {mem()}")
    t0 = time.perf_counter()
    engine = default_engine(Limits(max_chars=100_000))
    print(f"Engine load (cold start): {(time.perf_counter() - t0) * 1000:.0f} ms; after load current/peak MiB = {mem()}")

    stress_only = "stress" in sys.argv[1:]  # `python bench/final_measure.py stress`: only the hostile/dense rows
    if not stress_only:
        print("\n== Latency by size: sparse prose (~1 finding per 400 chars), balanced profile ==")
        print(HEADER)
        sparse = {}
        for n in (500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000):
            sparse[n] = measure(engine, sparse_text(n), runs_for(n))
            print(row("sparse", sparse[n]))
        weighted = sum(w * sparse[n]["mean"] for n, w in MIX.items())
        print(f"Assumed mix {MIX}: weighted mean = {weighted:.1f} ms (target: 100 ms average)")

        print("\n== Latency by size: PII-dense text (~1 finding per 40 chars) ==")
        print(HEADER)
        for n in (1_000, 5_000, 20_000, 100_000):
            print(row("dense", measure(engine, repeat_text(DENSE, n), runs_for(n))))

        print("\n== Non-English (NER skipped, patterns run), 5,000 chars ==")
        print(HEADER)
        print(row("spanish", measure(engine, repeat_text(SPANISH, 5_000), 30)))
        print(row("hebrew", measure(engine, repeat_text(HEBREW, 5_000), 30)))

    print("\n== Hostile input, whole engine, 100,000 chars (bounded time, status must report it) ==")
    print(HEADER)
    hostile = (
        ("digits", "1 2 "), ("plus-chain", "+1 2 3 4 5 6 7 8 9 "), ("at-signs", "a@"), ("no-space", "a"),
        # Dense VALID findings: junk cannot expose a cost that grows with the number of findings (the
        # first merge was quadratic: 12.7 s for 14k valid emails). These are the cases that can.
        ("valid-mail", "a@b.co "), ("valid-card", "4111 1111 1111 1111 "), ("valid-phone", "+44 20 7946 0958 "),
    )
    for label, unit in hostile:
        print(row(label, measure(engine, repeat_text(unit, 100_000), 3)))

    if stress_only:
        return
    print("\n== Phone numbers from several regions (lazy region metadata), memory before/after ==")
    before = mem()
    text = "call (415) 555-2671, 020 7946 0958, 612 345 678, 030 123456, 01 70 18 99 00, 03-1234-5678, 0412 345 678 now"
    for region in ("US", "GB", "ES", "DE", "FR", "IL", "JP", "IN", "BR", "AU"):
        engine.scan(text, region=region)
    print(f"current/peak MiB before {before} -> after {mem()}")

    print("\n== Repeated scans: memory growth over 2,000 mixed-size scans ==")
    texts = [sparse_text(500), sparse_text(1_000), sparse_text(2_000), sparse_text(5_000)]
    samples = [mem()[0]]
    for i in range(1, 2_001):
        engine.scan(texts[i % len(texts)])
        if i % 250 == 0:
            samples.append(mem()[0])
    print(f"current MiB every 250 scans: {samples}")
    print(f"growth first->last: {samples[-1] - samples[0]:+.1f} MiB; final current/peak MiB = {mem()}")
    snap = engine.metrics.snapshot()
    print(f"metrics (aggregate only): scans={snap['scans']}, status={snap['status']}, "
          f"entities={snap['entities']}, errors={snap['recognizer_errors']}, skips={snap['recognizer_skips']}")


if __name__ == "__main__":
    main()
