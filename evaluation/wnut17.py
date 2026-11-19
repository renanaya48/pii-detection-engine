"""Real-text PERSON sample from WNUT-17 (social-media text: Twitter, Reddit, YouTube, StackExchange).

Source:  https://github.com/leondz/emerging_entities_17  (README: "distributed under the CC-BY 4.0 license")
Cite:    Derczynski, Nichols, van Erp, Limsopatham (2017). Results of the WNUT2017 Shared Task on Novel and
         Emerging Entity Recognition. Workshop on Noisy User-generated Text, EMNLP.

Usage (repo root):
    python -m evaluation.wnut17 fetch                       # download + verify checksums into evaluation/data/raw
    python -m evaluation.wnut17 build [--n 400]             # sample dev and test sets into evaluation/data/

Only the ``person`` label is used (this engine detects PERSON); every other WNUT type is "not a person".

Known caveats, documented rather than hidden:
* Text is rebuilt from tokens (one per line) by a simple detokenizer, so it is close to, but not exactly,
  the original post. Gold offsets refer to the rebuilt text.
* WNUT annotation guidelines differ from those of the model's training data (OntoNotes 5), which lowers
  scores for reasons unrelated to engine quality.
* Possible overlap with the model's training data cannot be ruled out: OntoNotes is news, broadcast and
  web text, WNUT is social media, so overlap of documents is unlikely, but famous names occur in both.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/leondz/emerging_entities_17/master/"
FILES = {  # name -> sha256, checked at download time so the data cannot silently change
    "emerging.dev.conll": "e053b752b8155113ca66e7db08af5f2f5f43ab993694e4774f1ec5bad42312d8",
    "emerging.test.annotated": "2aa79b764e56ec9264a1b30fdd9b70195bd00ff400b62edd8f399d5f13c178f0",
}
DATA = Path(__file__).parent / "data"
RAW = DATA / "raw"
SPLITS = {"dev": ("emerging.dev.conll", 17), "test": ("emerging.test.annotated", 71)}

_NO_SPACE_BEFORE = {".", ",", "!", "?", ";", ":", "%", ")", "]", "}", "'s", "n't", "'re", "'ll", "'m", "'ve", "'d", "'t", "..."}
_NO_SPACE_AFTER = {"(", "[", "{", "$", "#"}
_HTML = {("&", "gt", ";"): ">", ("&", "lt", ";"): "<", ("&", "amp", ";"): "&"}  # Reddit escapes, split into tokens


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        with urllib.request.urlopen(BASE_URL + name, timeout=60) as response:  # fixed URL, never built from input
            data = response.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise SystemExit(f"checksum mismatch for {name}: {digest}")
        (RAW / name).write_bytes(data)
        print(f"fetched {name} ({len(data):,} bytes, sha256 ok)")


def parse_conll(path: Path) -> list[list[tuple[str, str]]]:
    """Sentences as lists of (token, tag); sentences are separated by blank lines."""
    sentences, current = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if current:
                sentences.append(current)
            current = []
            continue
        token, _, tag = line.partition("\t")
        current.append((token, tag.strip() or "O"))
    if current:
        sentences.append(current)
    return sentences


def _merge_html_escapes(sentence: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out, i = [], 0
    while i < len(sentence):
        triple = tuple(t for t, _ in sentence[i : i + 3])
        if triple in _HTML:
            out.append((_HTML[triple], "O"))
            i += 3
        else:
            out.append(sentence[i])
            i += 1
    return out


_CLITICS = {"s", "t", "re", "ll", "ve", "d", "m"}


def _merge_apostrophes(sentence: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """WNUT splits "won't" into wo / n / ' / t and "Kremlin's" into Kremlin / ' / s; rejoin them."""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(sentence):
        token, tag = sentence[i]
        following = sentence[i + 1][0] if i + 1 < len(sentence) else ""
        if token == "'" and following in _CLITICS and out:
            clitic = "'" + following
            if clitic == "'t" and out[-1][0].lower() == "n":  # wo + n + ' + t -> wo + n't
                out[-1] = (out[-1][0] + clitic, out[-1][1])
            else:
                out.append((clitic, sentence[i + 1][1]))
            i += 2
        else:
            out.append((token, tag))
            i += 1
    return out


def rebuild(sentence: list[tuple[str, str]]) -> tuple[str, list[tuple[int, int]]]:
    """Text plus gold PERSON spans (half-open code-point offsets into that text)."""
    tokens = _merge_apostrophes(_merge_html_escapes(sentence))
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []  # (start, end) of each token in the rebuilt text
    length = 0
    previous = ""
    for i, (token, _) in enumerate(tokens):
        if i and token not in _NO_SPACE_BEFORE and previous not in _NO_SPACE_AFTER:
            parts.append(" ")
            length += 1
        offsets.append((length, length + len(token)))
        parts.append(token)
        length += len(token)
        previous = token
    return "".join(parts), _person_spans([tag for _, tag in tokens], offsets)


def _person_spans(tags: list[str], offsets: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Turn BIO tags into character spans. An I-person with no open span starts one (as many corpora do)."""
    spans: list[tuple[int, int]] = []
    first: int | None = None  # index of the first token of the open span
    last = 0
    for i, tag in enumerate(tags):
        if tag == "B-person" or (tag == "I-person" and first is None):
            if first is not None:
                spans.append((offsets[first][0], offsets[last][1]))
            first = last = i
        elif tag == "I-person":
            last = i
        elif first is not None:
            spans.append((offsets[first][0], offsets[last][1]))
            first = None
    if first is not None:
        spans.append((offsets[first][0], offsets[last][1]))
    return spans


def build(n: int = 400) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for split, (filename, seed) in SPLITS.items():
        path = RAW / filename
        if not path.exists():
            raise SystemExit(f"missing {path}; run `python -m evaluation.wnut17 fetch` first")
        sentences = parse_conll(path)
        chosen = sorted(random.Random(seed).sample(range(len(sentences)), min(n, len(sentences))))
        out = DATA / f"wnut17_{split}.jsonl"
        persons = 0
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            for index in chosen:
                text, spans = rebuild(sentences[index])
                persons += len(spans)
                record = {"id": f"wnut17-{split}-{index}", "source": f"wnut17-{split}", "text": text,
                          "gold": [{"type": "PERSON", "start": s, "end": e} for s, e in spans]}
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{split}: {len(chosen)} of {len(sentences)} sentences (seed {seed}), {persons} PERSON mentions -> {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["fetch"]:
        fetch()
    elif args[:1] == ["build"]:
        build(int(args[args.index("--n") + 1]) if "--n" in args else 400)
    else:
        raise SystemExit(__doc__)
