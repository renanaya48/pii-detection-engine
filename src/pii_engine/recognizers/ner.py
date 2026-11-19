from __future__ import annotations

from ..types import EntityType, Evidence, ScanContext, Span

# Models load only from this fixed allowlist of installed package names; no input text,
# URL or path ever selects a model.
_MODELS = {"en": "en_core_web_sm"}
_PERSON_LABELS = {"PERSON", "PER"}  # the English model says PERSON; es/fr models say PER
_KEEP_PIPES = ("tok2vec", "ner")


def load_model(lang: str):
    """Load only the components NER needs. ``exclude`` (not ``disable``) so unused weights never reach memory."""
    import spacy

    name = _MODELS[lang]
    pipeline = spacy.info(name, silent=True)["pipeline"]
    return spacy.load(name, exclude=[p for p in pipeline if p not in _KEEP_PIPES])


class SpacyPersonRecognizer:
    name = "ner"
    requires_english = True  # the engine skips non-English segments and reports PARTIAL
    segmented = True  # NER memory/latency grow with length, so the engine feeds it bounded segments

    def __init__(self, nlp) -> None:
        self._nlp = nlp

    def analyze(self, text: str, ctx: ScanContext = ScanContext()) -> list[Span]:
        return [
            Span(EntityType.PERSON, ent.start_char, ent.end_char, Evidence.MODEL)
            for ent in self._nlp(text).ents
            if ent.label_ in _PERSON_LABELS and ent.end_char > ent.start_char
        ]
