import time

import pytest

from pii_engine.recognizers import EmailRecognizer

rec = EmailRecognizer(timeout_s=0.5)


def found(text):
    return [text[s.start : s.end] for s in rec.analyze(text)]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("write to john.smith+tag@example.com now", ["john.smith+tag@example.com"]),
        ("a@b.co.uk, c@d.org", ["a@b.co.uk", "c@d.org"]),
        ("Mail me at jane@example.com.", ["jane@example.com"]),  # trailing period excluded
        ("José@correo.es y ñandú@dominio.com", ["José@correo.es", "ñandú@dominio.com"]),
        ("user@xn--bcher-kva.example", ["user@xn--bcher-kva.example"]),
    ],
)
def test_detects_emails(text, expected):
    assert found(text) == expected


@pytest.mark.parametrize("text", ["no at sign here", "@nouser.com", "user@", "user@host", "a@1.23", "price 5@3"])
def test_rejects_non_emails(text):
    assert found(text) == []


def test_offsets_are_code_points_not_bytes():
    text = "😀 x@y.com"
    span = rec.analyze(text)[0]
    assert text[span.start : span.end] == "x@y.com" and span.start == 2


def test_adversarial_inputs_finish_quickly():
    for payload in ["a" * 200_000, "a@" * 50_000, "a." * 100_000, "a@" + "b." * 50_000]:
        t0 = time.perf_counter()
        rec.analyze(payload[:100_000])
        assert time.perf_counter() - t0 < 1.0
