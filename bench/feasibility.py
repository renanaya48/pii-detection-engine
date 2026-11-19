"""Step 1 feasibility experiment: can in-process spaCy NER fit 150 MB / 100 ms?

Usage (from the repo root, inside the `pii` conda env):
    python bench/feasibility.py            # full run: per-model + swap test, prints tables
    python bench/feasibility.py model en_core_web_sm   # internal: one model in a fresh process
    python bench/feasibility.py swap       # internal: load/evict sequence in one process

Each model is measured in its own fresh process so earlier loads cannot
inflate the numbers. The process is pinned to one core and the numeric
libraries are limited to one thread *before* any import that could read them.
"""
import os

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import gc
import json
import platform
import statistics
import subprocess
import sys
import time

import psutil

from _env import cpu_model, memory_mib, pin_to_one_core

PIPES_KEPT = ("tok2vec", "ner")
MODELS = {"en": "en_core_web_sm", "es": "es_core_news_sm", "fr": "fr_core_news_sm"}
SIZES_BYTES = (1024, 5120)
WARMUP_RUNS = 5
TIMED_RUNS = 40
MIB = 1024 * 1024  # MiB, not decimal MB

SENTENCES = {
    "en": [
        "Yesterday Emily Carter called Michael Johnson about the contract.",
        "The report was reviewed by Dr. Sarah Thompson and her colleague Robert Allen.",
        "Please forward the invoice to David Miller before the end of the week.",
        "Our team met with Jessica Brown and Daniel Wilson at the conference.",
    ],
    "es": [
        "Ayer Lucía Fernández llamó a Carlos Martínez para hablar del contrato.",
        "El informe fue revisado por la doctora Elena Ruiz y su colega Javier Gómez.",
        "Por favor envía la factura a Miguel Ángel Torres antes del viernes.",
        "Nuestro equipo se reunió con Carmen Navarro y Pablo Jiménez en la conferencia.",
    ],
    "fr": [
        "Hier, Camille Dubois a appelé Julien Martin au sujet du contrat.",
        "Le rapport a été relu par la docteure Sophie Lefèvre et son collègue Nicolas Moreau.",
        "Merci d'envoyer la facture à François Bertrand avant la fin de la semaine.",
        "Notre équipe a rencontré Élodie Garnier et Thomas Girard lors de la conférence.",
    ],
}


def build_text(lang: str, size_bytes: int) -> str:
    """Cycle through realistic sentences until the UTF-8 size is reached."""
    parts, size, i = [], 0, 0
    sentences = SENTENCES[lang]
    while size < size_bytes:
        s = sentences[i % len(sentences)]
        parts.append(s)
        size += len(s.encode("utf-8")) + 1
        i += 1
    return " ".join(parts)


def mem_mb() -> dict:
    current, peak = memory_mib()
    return {"rss": current, "peak_wset": peak}  # key name kept for the report columns


def load(spacy_mod, name: str):
    meta = spacy_mod.info(name, silent=True)
    exclude = [p for p in meta["pipeline"] if p not in PIPES_KEPT]
    return spacy_mod.load(name, exclude=exclude)


def run_model(lang: str) -> dict:
    pin_to_one_core()
    import spacy

    name = MODELS[lang]
    out = {"lang": lang, "model": name, "mem_baseline": mem_mb()}
    t0 = time.perf_counter()
    nlp = load(spacy, name)
    out["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    out["mem_after_load"] = mem_mb()
    out["pipes"] = nlp.pipe_names

    out["sizes"] = {}
    for size in SIZES_BYTES:
        text = build_text(lang, size)
        t0 = time.perf_counter()
        doc = nlp(text)
        first_ms = (time.perf_counter() - t0) * 1000
        for _ in range(WARMUP_RUNS):
            nlp(text)
        times = []
        for _ in range(TIMED_RUNS):
            t0 = time.perf_counter()
            nlp(text)
            times.append((time.perf_counter() - t0) * 1000)
        times.sort()
        out["sizes"][size] = {
            "bytes": len(text.encode("utf-8")),
            "chars": len(text),
            "tokens": len(doc),
            "first_ms": round(first_ms, 1),
            "mean_ms": round(statistics.fmean(times), 1),
            "p95_ms": round(times[int(0.95 * len(times)) - 1], 1),
        }
    out["mem_final"] = mem_mb()
    return out


def run_swap() -> dict:
    """Test A: single-model cache. en -> es -> fr -> en, measuring RSS after each load and evict."""
    pin_to_one_core()
    import spacy

    steps = [{"step": "start", **mem_mb()}]
    nlp = None
    for lang in ("en", "es", "fr", "en"):
        nlp = load(spacy, MODELS[lang])
        nlp(build_text(lang, SIZES_BYTES[0]))
        steps.append({"step": f"loaded {lang}", **mem_mb()})
        nlp = None
        gc.collect()
        steps.append({"step": f"evicted {lang} (gc)", **mem_mb()})
    return {"steps": steps}


def child(*args: str) -> dict:
    res = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, check=True)
    return json.loads(res.stdout.strip().splitlines()[-1])


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "model":
        print(json.dumps(run_model(sys.argv[2])))
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "swap":
        print(json.dumps(run_swap()))
        return

    import spacy

    print(f"CPU: {cpu_model()}")
    print(f"Python {platform.python_version()}, spaCy {spacy.__version__}, psutil {psutil.__version__}")
    print(f"Pinned to 1 core (affinity [0]), 1 BLAS/OMP thread, pipes kept: {PIPES_KEPT}")

    results = [child("model", lang) for lang in MODELS]
    print("\n== Per-model (fresh process each) ==")
    print("lang | model            | baseline MiB | after load MiB | peak MiB | load ms")
    for r in results:
        print(f"{r['lang']:4} | {r['model']:16} | {r['mem_baseline']['rss']:11} | "
              f"{r['mem_after_load']['rss']:13} | {r['mem_final']['peak_wset']:7} | {r['load_ms']}")
    print("\nlang | bytes | chars | tokens | first ms | warm mean ms | warm p95 ms")
    for r in results:
        for s in r["sizes"].values():
            print(f"{r['lang']:4} | {s['bytes']:5} | {s['chars']:5} | {s['tokens']:6} | "
                  f"{s['first_ms']:8} | {s['mean_ms']:12} | {s['p95_ms']}")

    print("\n== Test A: single-model cache, en -> es -> fr -> en ==")
    print("step                | current MiB | peak MiB")
    for s in child("swap")["steps"]:
        print(f"{s['step']:19} | {s['rss']:10} | {s['peak_wset']}")


if __name__ == "__main__":
    main()
