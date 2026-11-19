"""Feasibility probe: could a quantised DistilBERT NER (ONNX Runtime) replace spaCy within 150 MB / 100 ms?

NOT part of the engine. Run in a SEPARATE environment so the frozen one is untouched:
    conda create -n pii-probe python=3.12 && conda activate pii-probe
    pip install onnxruntime tokenizers numpy psutil regex phonenumbers
    # model (Apache-2.0): https://huggingface.co/tarekziade/distilbert-NER  (int8 export of dslim/distilbert-NER)
    #   download onnx/model_quantized.onnx, tokenizer.json, config.json into one directory
    python bench/probes/transformer_probe.py --model-dir DIR [--no-arena] [--quality]

Reports whole-process memory (with the engine's pattern-layer imports), whole-call latency by input size on one core
and one thread, and (with --quality) PERSON precision/recall on DEV data only (WNUT-17 dev sample, synthetic dev).
The held-out test split is never read.
"""
import argparse
import importlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_var] = "1"

import psutil

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "src"), str(REPO), str(REPO / "bench")]
MIB = 1 << 20  # memory is reported in MiB, not decimal MB
INFINITE_MARGIN = 10**9
WINDOW, OVERLAP = 254, 32  # tokens per model call (+ [CLS] and [SEP] = 256), tokens shared by neighbouring windows


def memory() -> str:
    info = psutil.Process().memory_info()
    peak = getattr(info, "peak_wset", info.rss)
    return f"{info.rss / MIB:6.1f} MiB (peak {peak / MIB:6.1f})"


class PersonTagger:
    """Token classification over overlapping windows; returns character spans of B-PER / I-PER runs."""

    def __init__(self, model_dir: Path, arena: bool, model_file: str = "model_quantized.onnx", prepacking: bool = True) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self.labels = {int(k): v for k, v in config["id2label"].items()}
        options = ort.SessionOptions()
        options.intra_op_num_threads = options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.enable_cpu_mem_arena = arena
        if not prepacking:  # prepacking keeps a second, re-laid-out copy of the weights
            options.add_session_config_entry("session.disable_prepacking", "1")
        self.session = ort.InferenceSession(str(model_dir / model_file), options, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.cls, self.sep = self.tokenizer.token_to_id("[CLS]"), self.tokenizer.token_to_id("[SEP]")

    def _predict(self, ids: list[int]) -> list[int]:
        import numpy as np

        window = [self.cls, *ids, self.sep]
        feeds = {"input_ids": np.array([window], dtype=np.int64), "attention_mask": np.ones((1, len(window)), dtype=np.int64)}
        logits = self.session.run(None, {k: v for k, v in feeds.items() if k in self.input_names})[0][0]
        return [int(i) for i in logits.argmax(-1)[1:-1]]  # drop the [CLS] and [SEP] positions

    def spans(self, text: str) -> list[tuple[int, int]]:
        encoding = self.tokenizer.encode(text, add_special_tokens=False)
        ids, offsets = encoding.ids, encoding.offsets
        n = len(ids)
        best: list[tuple[int, int] | None] = [None] * n  # (margin, label): keep the window where a token is furthest from an edge
        start = 0
        while True:
            end = min(start + WINDOW, n)
            labels = self._predict(ids[start:end])
            for j, label in enumerate(labels):
                margin = min(j if start > 0 else INFINITE_MARGIN, (end - start - 1 - j) if end < n else INFINITE_MARGIN)
                if best[start + j] is None or margin > best[start + j][0]:
                    best[start + j] = (margin, label)
            if end == n:
                break
            start = end - OVERLAP
        return self._merge(offsets, [b[1] if b else 0 for b in best])

    def _merge(self, offsets, labels) -> list[tuple[int, int]]:
        spans, current = [], None
        for (start, end), label in zip(offsets, labels):
            name = self.labels[label]
            if name.endswith("PER"):
                if current is not None and (name == "I-PER" or start == current[1]):  # continuation, or a glued word-piece
                    current[1] = end
                else:
                    if current is not None:
                        spans.append(tuple(current))
                    current = [start, end]
            elif current is not None:
                spans.append(tuple(current))
                current = None
        if current is not None:
            spans.append(tuple(current))
        return spans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--no-arena", action="store_true", help="disable the ONNX Runtime CPU memory arena")
    parser.add_argument("--model-file", default="model_quantized.onnx", help="model file name inside --model-dir")
    parser.add_argument("--no-prepacking", action="store_true", help="disable weight prepacking (less memory, slower)")
    parser.add_argument("--quality", action="store_true", help="also score PERSON on DEV data")
    args = parser.parse_args()

    proc = psutil.Process()
    try:
        proc.cpu_affinity([proc.cpu_affinity()[0]])
    except (AttributeError, NotImplementedError, OSError):
        print("(no CPU affinity API: not pinned)")
    print("python + psutil:                   ", memory())
    for name in ("numpy", "onnxruntime", "tokenizers"):  # imported one by one only to attribute memory to each stage
        importlib.import_module(name)
    print("+ numpy, onnxruntime, tokenizers:  ", memory())
    importlib.import_module("pii_engine.engine")  # regex, phonenumbers and the pattern recognizers
    print("+ the engine's pattern layer:      ", memory())
    started = time.perf_counter()
    tagger = PersonTagger(args.model_dir, arena=not args.no_arena, model_file=args.model_file, prepacking=not args.no_prepacking)
    print(f"+ model loaded ({(time.perf_counter() - started) * 1000:.0f} ms):        ", memory())
    tagger.spans("Please send the invoice to Emily Carter before Friday.")  # warm-up
    print("after the first inference:         ", memory())

    from final_measure import sparse_text

    print("whole NER call on sparse prose, mean / max of 12 warm runs:")
    for size in (500, 1_000, 2_000, 5_000):
        text = sparse_text(size)
        tagger.spans(text)
        times = []
        for _ in range(12):
            t0 = time.perf_counter()
            tagger.spans(text)
            times.append((time.perf_counter() - t0) * 1000)
        print(f"  {len(text):>5} chars: mean {statistics.fmean(times):6.1f} ms, max {max(times):6.1f} ms")
    print("after the latency runs:            ", memory())

    if args.quality:
        from evaluation.metrics import Mention, aggregate, score_document

        for label, name in (("WNUT-17 dev", "wnut17_dev.jsonl"), ("synthetic dev", "synthetic_dev.jsonl")):
            per_record = []
            for line in (REPO / "evaluation" / "data" / name).read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                predicted = [Mention("PERSON", s, e) for s, e in tagger.spans(record["text"])]
                gold = [Mention("PERSON", g["start"], g["end"]) for g in record["gold"] if g["type"] == "PERSON"]
                per_record.append(score_document(gold, predicted))
            c = aggregate(per_record)["PERSON"]
            print(f"{label:<14} PERSON  precision {100 * c.precision:5.1f}  recall {100 * c.recall:5.1f}  F1 {100 * c.f1:5.1f}  (pred {c.pred}, gold {c.gold})")


if __name__ == "__main__":
    main()
