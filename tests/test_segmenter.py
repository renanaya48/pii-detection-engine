import re

import pytest

from pii_engine.config import Limits
from pii_engine.engine import Engine
from pii_engine.segmenter import Segment, segment
from pii_engine.types import EntityType as T
from pii_engine.types import Evidence as E
from pii_engine.types import ScanStatus, Span

FILLER = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor " * 8).strip()


# ---- segmentation itself -------------------------------------------------------------------


def test_short_text_is_one_segment_covering_everything():
    segs = segment("hello world", 100, 10)
    assert segs == [Segment(0, "hello world", True, True)]


def test_empty_text_is_one_empty_segment():
    assert segment("", 100, 10) == [Segment(0, "", True, True)]


@pytest.mark.parametrize("size,overlap", [(10, 5), (10, 6), (10, 0), (10, -1)])
def test_invalid_parameters_are_rejected(size, overlap):
    with pytest.raises(ValueError):
        segment("x" * 50, size, overlap)


@pytest.mark.parametrize("text", [FILLER, "word " * 5_000, "לורם איפסום " * 300, "😀 emoji " * 400])
def test_segments_cover_the_text_and_overlap_by_at_least_the_overlap(text):
    size, overlap = 200, 40
    segs = segment(text, size, overlap)
    assert segs[0].first and segs[-1].last and not any(s.first or s.last for s in segs[1:-1])
    assert segs[0].start == 0 and segs[-1].start + len(segs[-1].text) == len(text)
    for s in segs:
        assert text[s.start : s.start + len(s.text)] == s.text  # offsets map back exactly
        assert len(s.text) <= size
    for a, b in zip(segs, segs[1:]):
        assert b.start > a.start  # progress
        assert (a.start + len(a.text)) - b.start >= overlap  # guaranteed shared region
        assert b.start <= a.start + len(a.text)  # no gap


def test_segments_break_at_whitespace_when_it_exists():
    segs = segment(FILLER, 200, 40)
    for s in segs[:-1]:
        assert s.text[-1].isspace()  # ends right after a space
    for s in segs[1:]:
        assert not s.text[0].isspace()  # starts at a word


@pytest.mark.parametrize("text", ["a" * 10_000, "😀" * 5_000])
def test_text_without_whitespace_is_hard_cut_and_terminates(text):
    segs = segment(text, 300, 50)
    assert len(segs) > 1
    assert segs[-1].start + len(segs[-1].text) == len(text)


def test_keep_drops_spans_touching_an_interior_edge_only():
    middle = Segment(100, "x" * 50, first=False, last=False)
    assert not middle.keep(Span(T.PERSON, 0, 5, E.MODEL))  # touches left interior edge
    assert not middle.keep(Span(T.PERSON, 45, 50, E.MODEL))  # touches right interior edge
    assert middle.keep(Span(T.PERSON, 1, 49, E.MODEL))
    first = Segment(0, "x" * 50, first=True, last=False)
    assert first.keep(Span(T.PERSON, 0, 5, E.MODEL))  # document start is a real start
    last = Segment(90, "x" * 50, first=False, last=True)
    assert last.keep(Span(T.PERSON, 45, 50, E.MODEL))  # document end is a real end


def test_100k_chars_split_into_bounded_segments():
    text = ("word " * 30_000)[:100_000]
    segs = segment(text, 4_000, 200)
    assert max(len(s.text) for s in segs) <= 4_000
    assert 25 <= len(segs) <= 30  # ~overhead of the overlap only


# ---- through the engine, with a stub "NER" that depends on segment content ---------------------


class _NameStub:
    """Finds 'Firstname Lastname' in whatever text it is given, like a model that sees only its segment."""

    name = "ner"
    segmented = True

    def analyze(self, text, ctx=None):
        return [Span(T.PERSON, m.start(), m.end(), E.MODEL) for m in re.finditer(r"[A-Z][a-z]+ [A-Z][a-z]+", text)]


SMALL = Limits(segment_chars=100, segment_overlap=30)
NAME = "Emily Carter"


def test_a_name_at_every_offset_is_found_whole_exactly_once():
    """The boundary sweep: whichever way segment edges fall inside or around the name."""
    engine = Engine([_NameStub()], SMALL)
    for p in range(len(FILLER) + 1):
        text = f"{FILLER[:p]} {NAME} {FILLER[p:]}"
        spans = engine.scan(text).spans
        assert [(s.start, s.end) for s in spans] == [(p + 1, p + 1 + len(NAME))], p


def test_names_at_document_start_and_end_are_found():
    engine = Engine([_NameStub()], SMALL)
    for text in (f"{NAME} {FILLER}", f"{FILLER} {NAME}"):
        assert [text[s.start : s.end] for s in engine.scan(text).spans] == [NAME]


def test_offsets_are_correct_after_unicode_prefixes():
    engine = Engine([_NameStub()], SMALL)
    prefix = "😀 שלום עולם " * 20
    text = f"{prefix}{NAME} {FILLER}"
    assert [text[s.start : s.end] for s in engine.scan(text).spans] == [NAME]


def test_many_names_across_many_segments_are_each_found_once():
    names = ["Anna Smith", "Bob Jones", "Carol White", "Dave Brown"] * 10
    text = " ".join(f"{FILLER[:40]} {n}" for n in names)
    result = Engine([_NameStub()], SMALL).scan(text)
    assert sorted(text[s.start : s.end] for s in result.spans) == sorted(names)
    assert result.status is ScanStatus.COMPLETE


# ---- status aggregation across segments -----------------------------------------------------


class _FailsOnMarker(_NameStub):
    def analyze(self, text, ctx=None):
        if "BOOM" in text:
            raise RuntimeError("model crashed")
        return super().analyze(text, ctx)


def test_one_failing_segment_gives_partial_and_keeps_findings_from_the_others():
    text = f"{NAME} {FILLER} BOOM {FILLER} Anna Smith"
    engine = Engine([_FailsOnMarker()], SMALL)
    result = engine.scan(text)
    assert result.status is ScanStatus.PARTIAL
    assert {text[s.start : s.end] for s in result.spans} == {NAME, "Anna Smith"}


def test_all_segments_failing_is_failed():
    class _AlwaysFails(_NameStub):
        def analyze(self, text, ctx=None):
            raise RuntimeError("down")

    assert Engine([_AlwaysFails()], SMALL).scan(f"{FILLER} {FILLER}").status is ScanStatus.FAILED


class _GatedNameStub(_NameStub):
    requires_english = True

    def __init__(self):
        self.calls = 0

    def analyze(self, text, ctx=None):
        self.calls += 1
        return super().analyze(text, ctx)


def test_language_is_decided_per_segment_not_once_for_the_whole_text():
    english = "Please send the invoice to Emily Carter and tell him that we will be there on time. " * 3
    hebrew = "שלום, אני רוצה לשלוח את החשבונית לדוד כהן עד יום שישי בבוקר, תודה רבה לכם. " * 12  # fills whole segments
    text = english + hebrew + english
    stub = _GatedNameStub()
    engine = Engine([stub], Limits(segment_chars=250, segment_overlap=40))
    result = engine.scan(text)
    total_segments = len(segment(text, 250, 40))
    assert 0 < stub.calls < total_segments  # Hebrew-only segments were skipped, English ones ran
    assert result.status is ScanStatus.PARTIAL
    assert engine.metrics.snapshot()["recognizer_skips"]["ner:language"] >= 1
    assert any(text[s.start : s.end] == NAME for s in result.spans)


def test_segment_without_letters_is_skipped_silently():
    stub = _GatedNameStub()
    engine = Engine([stub], Limits(segment_chars=100, segment_overlap=20))
    result = engine.scan("1234 5678 " * 100)
    assert stub.calls == 0 and result.status is ScanStatus.COMPLETE
