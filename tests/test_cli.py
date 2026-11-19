import io
import json

import pytest

from pii_engine.__main__ import main
from pii_engine.engine import Engine
from pii_engine.recognizers import CreditCardRecognizer, EmailRecognizer, PhoneRecognizer


def patterns_only():
    return Engine([EmailRecognizer(0.5), CreditCardRecognizer(0.5), PhoneRecognizer()])


def run(argv, capsys, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(argv, engine_factory=patterns_only)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_prints_only_the_public_contract(capsys):
    code, out, _ = run(["mail a@b.com now"], capsys)
    assert code == 0
    assert json.loads(out) == {"status": "complete", "results": [{"type": "EMAIL", "start": 5, "end": 12}]}


def test_never_echoes_the_input(capsys):
    code, out, err = run(["secret-token jane@example.com"], capsys)
    assert "secret-token" not in out + err and "jane@example.com" not in out + err


def test_reads_stdin_when_no_text_or_dash(capsys, monkeypatch):
    for argv in ([], ["-"]):
        code, out, _ = run(argv, capsys, stdin="a@b.com", monkeypatch=monkeypatch)
        assert json.loads(out)["results"][0]["type"] == "EMAIL"


def test_reads_a_file(capsys, tmp_path):
    path = tmp_path / "in.txt"
    path.write_text("call +44 20 7946 0958", encoding="utf-8")
    code, out, _ = run(["--file", str(path)], capsys)
    assert json.loads(out)["results"][0]["type"] == "PHONE"


def test_region_and_profile_options(capsys):
    _, out, _ = run(["call (415) 555-2671", "--region", "us"], capsys)
    assert json.loads(out)["results"][0]["type"] == "PHONE"
    _, out, _ = run(["call (415) 555-2671"], capsys)
    assert json.loads(out)["results"] == []


def test_unicode_output_is_not_escaped_and_offsets_are_code_points(capsys):
    _, out, _ = run(["שלום 😀 a@b.com"], capsys)
    assert json.loads(out)["results"] == [{"type": "EMAIL", "start": 7, "end": 14}]


def test_failed_status_gives_exit_code_1(capsys):
    code, out, _ = run(["a@b.com", "--region", "USA"], capsys)
    assert code == 1 and json.loads(out) == {"status": "failed", "results": []}


def test_oversized_input_is_failed_not_loaded_whole(capsys, monkeypatch):
    code, out, _ = run([], capsys, stdin="x" * 500_000, monkeypatch=monkeypatch)
    assert code == 1 and json.loads(out)["status"] == "failed"


@pytest.mark.parametrize("limit", [50, 100_000, 300_000])
def test_input_is_read_with_the_engines_limit_never_silently_truncated(capsys, monkeypatch, tmp_path, limit):
    """Input one character over the ENGINE's limit must fail, whatever that limit is."""
    from pii_engine.config import Limits

    def factory():
        return Engine([EmailRecognizer(0.5)], Limits(max_chars=limit))

    over = "x" * limit + "a@b.com"  # the email sits beyond the limit: a silent prefix cut would hide it
    path = tmp_path / "over.txt"
    path.write_text(over, encoding="utf-8")
    for argv, stdin in (([], over), (["--file", str(path)], None)):
        if stdin is not None:
            monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = main(argv, engine_factory=factory)
        assert code == 1 and json.loads(capsys.readouterr().out)["status"] == "failed"

    exact = "x" * (limit - 8) + " a@b.com"  # exactly at the limit is accepted
    path.write_text(exact, encoding="utf-8")
    assert main(["--file", str(path)], engine_factory=factory) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["type"] == "EMAIL"


def test_missing_file_and_bad_encoding_report_class_only(capsys, tmp_path):
    code, _, err = run(["--file", str(tmp_path / "nope.txt")], capsys)
    assert code == 2 and "FileNotFoundError" in err
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe\x00 secret")
    code, _, err = run(["--file", str(bad)], capsys)
    assert code == 2 and "UnicodeDecodeError" in err and "secret" not in err


def test_text_and_file_together_is_a_usage_error(capsys, tmp_path):
    path = tmp_path / "in.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["text", "--file", str(path)], engine_factory=patterns_only)
    assert exc.value.code == 2
