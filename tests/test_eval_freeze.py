"""The freeze ties a held-out result to an exact state, and the final run is refused if that state changed."""
import json

import pytest

from evaluation import __main__ as cli
from evaluation import freeze


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A tiny fake repo so tests can change 'engine', 'evaluation' and 'data' files freely."""
    repo = tmp_path / "repo"
    (repo / "src" / "pii_engine").mkdir(parents=True)
    (repo / "evaluation" / "data").mkdir(parents=True)
    (repo / "src" / "pii_engine" / "engine.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "evaluation" / "runner.py").write_text("y = 1\n", encoding="utf-8")
    (repo / "evaluation" / "data" / "set.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    (repo / "requirements-tested.txt").write_text("spacy==3.8.18\n", encoding="utf-8")
    monkeypatch.setattr(freeze, "REPO", repo)
    monkeypatch.setattr(freeze, "ROOT", repo / "evaluation")
    monkeypatch.setattr(freeze, "FREEZE_FILE", repo / "evaluation" / "FREEZE.json")
    monkeypatch.setattr(freeze, "_model_version", lambda: "en_core_web_sm 3.8.0, spacy 3.8.18")
    return repo


def test_no_freeze_file_means_nothing_is_frozen(sandbox):
    assert freeze.differences() == ["no freeze recorded (run `python -m evaluation --freeze` first)"]


def test_a_fresh_freeze_has_no_differences(sandbox):
    freeze.write_freeze()
    assert freeze.differences() == []


@pytest.mark.parametrize(
    "relative,label",
    [
        ("src/pii_engine/engine.py", "engine_source"),
        ("evaluation/runner.py", "evaluation_code"),
        ("evaluation/data/set.jsonl", "evaluation_data"),
        ("requirements-tested.txt", "dependencies"),
    ],
)
def test_changing_any_component_is_detected_by_name(sandbox, relative, label):
    freeze.write_freeze()
    (sandbox / relative).write_text("changed\n", encoding="utf-8")
    assert freeze.differences() == [f"{label} changed since the freeze"]


def test_a_new_file_in_a_frozen_area_is_detected(sandbox):
    freeze.write_freeze()
    (sandbox / "src" / "pii_engine" / "extra.py").write_text("z = 1\n", encoding="utf-8")
    assert "engine_source changed since the freeze" in freeze.differences()


def test_model_or_python_change_is_detected(sandbox, monkeypatch):
    freeze.write_freeze()
    monkeypatch.setattr(freeze, "_model_version", lambda: "en_core_web_sm 3.9.0, spacy 3.8.18")
    assert any(d.startswith("model changed") for d in freeze.differences())


def test_documentation_and_results_do_not_unfreeze(sandbox):
    freeze.write_freeze()
    (sandbox / "evaluation" / "README.md").write_text("edited docs\n", encoding="utf-8")
    (sandbox / "evaluation" / "results").mkdir()
    (sandbox / "evaluation" / "results" / "dev.json").write_text("{}", encoding="utf-8")
    assert freeze.differences() == []


def test_line_endings_do_not_change_the_hash(sandbox):
    freeze.write_freeze()
    (sandbox / "src" / "pii_engine" / "engine.py").write_bytes(b"x = 1\r\n")
    assert freeze.differences() == []


def test_freeze_id_ignores_the_creation_time_but_tracks_the_state(sandbox):
    first = freeze.write_freeze()
    second = freeze.manifest()  # a later timestamp, same state
    assert first["created"] <= second["created"] and freeze.freeze_id(first) == freeze.freeze_id(second)
    (sandbox / "evaluation" / "runner.py").write_text("y = 2\n", encoding="utf-8")
    assert freeze.freeze_id(freeze.manifest()) != freeze.freeze_id(first)


# ---- wiring into the held-out run -----------------------------------------------------------------------


@pytest.fixture
def guarded(sandbox, tmp_path, monkeypatch):
    results = tmp_path / "results"
    monkeypatch.setattr(cli, "RESULTS", results)
    monkeypatch.setattr(cli, "SRC", sandbox / "src" / "pii_engine")
    monkeypatch.setattr(cli, "DATA", sandbox / "evaluation" / "data")
    monkeypatch.setattr(cli, "SETS", {"s": cli.Dataset("set.jsonl", None, False)})
    return results


def test_the_final_run_is_refused_without_a_freeze(guarded):
    with pytest.raises(SystemExit, match="frozen state"):
        cli.guard_test_split(final=True, again=False)


def test_the_final_run_is_refused_if_anything_changed_after_the_freeze(guarded, sandbox):
    freeze.write_freeze()
    (sandbox / "evaluation" / "runner.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="evaluation_code changed"):
        cli.guard_test_split(final=True, again=False)


def test_the_final_run_is_allowed_on_a_frozen_state_and_logs_the_freeze_id(guarded, sandbox):
    data = freeze.write_freeze()
    cli.guard_test_split(final=True, again=False)
    cli.log_test_event(again=False, status="started")
    assert f"freeze={freeze.freeze_id(data)}" in (guarded / "test_runs.log").read_text(encoding="utf-8")


def test_the_freeze_command_writes_the_manifest(guarded, sandbox):
    assert cli.main(["--freeze"]) == 0
    assert set(json.loads((sandbox / "evaluation" / "FREEZE.json").read_text(encoding="utf-8"))["components"]) == {
        "engine_source", "evaluation_code", "evaluation_data", "dependencies"}


def test_split_is_required_unless_freezing(guarded):
    with pytest.raises(SystemExit):
        cli.main([])
