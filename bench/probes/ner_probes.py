"""Two PERSON-quality probes for the existing spaCy engine. Scored on DEV material only; the held-out split is never read.

    python bench/probes/ner_probes.py cheap              # non-training changes: ALL-CAPS normalisation, name-context rules
    python bench/probes/ner_probes.py finetune [epochs]  # fine-tune the NER on the WNUT-17 TRAIN file (CC-BY 4.0)

Why these are probes and not engine changes: changing the engine after the held-out run would end its held-out status
(see evaluation/README.md). They exist to find out whether a change is worth that cost.

Note on bias: the synthetic generator writes "my name is" and "Dr." into its templates, so cue rules look better on that
data than they can on real text. WNUT dev is the only fair judge for them. The synthetic TEST file has already been
looked at, so for these probes it counts as dev data and is labelled so.
"""
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_var] = "1"

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "src"), str(REPO)]
DATA = REPO / "evaluation" / "data"
TRAIN_URL = "https://raw.githubusercontent.com/leondz/emerging_entities_17/master/wnut17train.conll"
TRAIN_SHA256 = "731820e13f71af324c6b55a1575ec2ce59fbaa2a0806f8f0400b98d56cd6a7a5"


def load(name: str, groups: set[str] | None = None) -> list[dict]:
    rows = [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if not groups or r["group"] in groups]


def person_score(predict, rows: list[dict]) -> str:
    """``predict(text) -> set of (start, end)``; exact-match PERSON precision/recall/F1 and coverage recall."""
    from evaluation.metrics import Mention, aggregate, score_document

    per_record = []
    for row in rows:
        gold = [Mention("PERSON", g["start"], g["end"]) for g in row["gold"] if g["type"] == "PERSON"]
        per_record.append(score_document(gold, [Mention("PERSON", s, e) for s, e in sorted(predict(row["text"]))]))
    c = aggregate(per_record)["PERSON"]
    f = lambda v: "  n/a" if v is None else f"{100 * v:5.1f}"
    return f"P {f(c.precision)} R {f(c.recall)} F1 {f(c.f1)} coverage {f(c.coverage_recall)} (pred {c.pred}/gold {c.gold})"


def datasets() -> dict[str, list[dict]]:
    return {
        "WNUT-17 dev (real text)": load("wnut17_dev.jsonl"),
        "synthetic dev, person+mixed": load("synthetic_dev.jsonl", {"person", "mixed"}),
        "synthetic 'test', person+mixed (now dev)": load("synthetic_test.jsonl", {"person", "mixed"}),
    }


_ALL_CAPS = re.compile(r"\b[A-Z]{2,}\b")
_CUE = re.compile(r"(?i:\bmy name is|\bname:|\bdear|\bmr\.?|\bmrs\.?|\bms\.?|\bmiss|\bdr\.?|\bprof\.?)\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})")


def normalise_case(text: str) -> str:
    """Title-case ALL-CAPS words for the model only. Offsets are preserved: a word whose case mapping would change
    its length is left as it is."""
    def fix(match: re.Match) -> str:
        word = match.group()
        titled = word.capitalize()
        return titled if len(titled) == len(word) else word

    return _ALL_CAPS.sub(fix, text)


def cheap() -> None:
    from pii_engine.recognizers import load_model

    nlp = load_model("en")

    def model_spans(text):
        return {(e.start_char, e.end_char) for e in nlp(text).ents if e.label_ == "PERSON"}

    variants = {
        "baseline": model_spans,
        "ALL-CAPS normalisation": lambda t: model_spans(normalise_case(t)),
        "name-context rules": lambda t: model_spans(t) | {(m.start(1), m.end(1)) for m in _CUE.finditer(t)},
    }
    for name, predict in variants.items():
        print(f"--- {name}")
        for label, rows in datasets().items():
            print(f"   {label:<44} {person_score(predict, rows)}")


def finetune(epochs: int) -> None:
    import spacy
    from spacy.training import Example
    from spacy.util import compounding, minibatch

    from evaluation.wnut17 import RAW, parse_conll, rebuild

    train_path = RAW / "wnut17train.conll"
    if not train_path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(TRAIN_URL, timeout=60).read()  # fixed URL, verified below
        if hashlib.sha256(data).hexdigest() != TRAIN_SHA256:
            raise SystemExit("checksum mismatch for the WNUT-17 train file")
        train_path.write_bytes(data)

    nlp = spacy.load("en_core_web_sm", exclude=["tagger", "parser", "attribute_ruler", "lemmatizer"])
    train = [rebuild(sentence) for sentence in parse_conll(train_path)]
    print(f"train sentences {len(train)}, person mentions {sum(len(spans) for _, spans in train)}")
    dev = datasets()["WNUT-17 dev (real text)"]

    def predict(text):
        return {(e.start_char, e.end_char) for e in nlp(text).ents if e.label_ == "PERSON"}

    print("baseline:", person_score(predict, dev))
    examples = [Example.from_dict(nlp.make_doc(text), {"entities": [(s, e, "PERSON") for s, e in spans]}) for text, spans in train]
    random.seed(0)
    optimizer = nlp.resume_training()
    started = time.time()
    for epoch in range(1, epochs + 1):
        random.shuffle(examples)
        losses: dict = {}
        for batch in minibatch(examples, size=compounding(4.0, 32.0, 1.001)):
            nlp.update(batch, sgd=optimizer, drop=0.3, losses=losses)
        print(f"epoch {epoch}: loss {losses.get('ner', 0):7.1f} | dev {person_score(predict, dev)} | {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "cheap":
        cheap()
    elif mode == "finetune":
        finetune(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
    else:
        raise SystemExit(__doc__)
