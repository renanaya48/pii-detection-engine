"""The well-cased prompt set: parser, the real author file, and the build / run-once protocol."""
import json

import pytest

from evaluation.prompts import __main__ as prompts
from evaluation.prompts.parse import parse_prompt, split_entries, to_records


# ---- parser ---------------------------------------------------------------------------------------------


def test_markers_are_removed_and_offsets_slice_to_the_names():
    text, gold = parse_prompt("Ask [[Dana Cohen]] and [[Lee]] to call.")
    assert text == "Ask Dana Cohen and Lee to call."
    assert [(g["type"], text[g["start"] : g["end"]]) for g in gold] == [("PERSON", "Dana Cohen"), ("PERSON", "Lee")]


def test_other_entity_types_and_unicode_offsets():
    text, gold = parse_prompt("😀 Mail [[José Núñez]] at [[EMAIL:jose@example.com]] or [[PHONE:+34 612 345 678]].")
    assert [(g["type"], text[g["start"] : g["end"]]) for g in gold] == [
        ("PERSON", "José Núñez"), ("EMAIL", "jose@example.com"), ("PHONE", "+34 612 345 678")]


def test_entries_comments_and_multiline_prompts():
    raw = "## comment\nFirst [[A B]]\nsecond line\n---\n## another\n---\nSecond one\n---\n"
    entries = split_entries(raw)
    assert entries == ["First [[A B]]\nsecond line", "Second one"]
    assert parse_prompt(entries[0])[0] == "First A B\nsecond line"


@pytest.mark.parametrize("bad", ["Dr. [[Dr. Who]]", "[[Mrs. Delgado]] called", "[[Professor Xavier]]", "[[Uncle Bob]]"])
def test_titles_inside_markers_are_rejected(bad):
    with pytest.raises(ValueError, match="titles belong outside"):
        parse_prompt(bad)


@pytest.mark.parametrize("bad", ["[[ Padded ]]", "[[]]", "[[Open", "Close]]", "[[Nested [[Name]]]]"])
def test_malformed_markers_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_prompt(bad)


def test_titles_outside_the_markers_are_fine():
    text, gold = parse_prompt("Dr. [[Priya Nair]] and Mrs. [[Delgado]]")
    assert [text[g["start"] : g["end"]] for g in gold] == ["Priya Nair", "Delgado"]


def test_groups_distinguish_names_other_pii_and_nothing():
    records = to_records("Hi [[Ann Lee]]\n---\nMail [[EMAIL:a@b.com]]\n---\nPlain text", "author")
    assert [r["group"] for r in records] == ["names_author", "other_pii_author", "negative_author"]
    assert [r["id"] for r in records] == ["prompts-author-001", "prompts-author-002", "prompts-author-003"]


# ---- the real author file -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def author_records():
    return to_records(prompts.SOURCES["author"].read_text(encoding="utf-8"), "author")


def test_author_file_has_the_stated_composition(author_records):
    with_names = sum(1 for r in author_records if r["group"] == "names_author")
    negatives = sum(1 for r in author_records if r["group"] == "negative_author")
    assert 95 <= with_names <= 110 and 45 <= negatives <= 55, (with_names, negatives)
    assert with_names + negatives == len(author_records)  # no entry is neither (other PII always comes with a name)


def test_author_prompts_are_unique_and_every_label_slices_to_text(author_records):
    texts = [r["text"] for r in author_records]
    assert len(texts) == len(set(texts))
    for r in author_records:
        for g in r["gold"]:
            assert r["text"][g["start"] : g["end"]].strip() and 0 <= g["start"] < g["end"] <= len(r["text"])


def test_author_names_are_not_titles_and_are_capitalised(author_records):
    for r in author_records:
        for g in r["gold"]:
            surface = r["text"][g["start"] : g["end"]]
            if g["type"] == "PERSON":
                assert surface[0].isupper() and "\n" not in surface, surface


def test_author_negative_prompts_contain_capitalised_non_names(author_records):
    """Hard negatives must really be there: places, companies and products with capital letters."""
    text = " ".join(r["text"] for r in author_records if r["group"] == "negative_author")
    for word in ("Lisbon", "Kubernetes", "Samsung", "Austin", "Jordan", "Windows Defender", "Contoso", "Brooklyn"):
        assert word in text


def test_the_user_file_always_parses_cleanly_whatever_the_owner_has_added():
    """The owner edits this file by hand, so any mistake (a title inside a marker, an unbalanced bracket) must surface
    here with a clear message instead of at run time."""
    records = to_records(prompts.SOURCES["user"].read_text(encoding="utf-8"), "user")
    for r in records:
        assert r["text"].strip() and all(r["text"][g["start"] : g["end"]].strip() for g in r["gold"])
    assert len({r["id"] for r in records}) == len(records)


# ---- build and run protocol -----------------------------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    author, user = tmp_path / "author.txt", tmp_path / "user.txt"
    author.write_text("Hi [[Ann Lee]]\n---\nA plain prompt about Paris\n", encoding="utf-8")
    user.write_text("Call [[Bo Chen]]\n", encoding="utf-8")
    monkeypatch.setattr(prompts, "SOURCES", {"author": author, "user": user})
    monkeypatch.setattr(prompts, "DATA", tmp_path / "prompts.jsonl")
    monkeypatch.setattr(prompts, "MANIFEST", tmp_path / "MANIFEST.json")
    monkeypatch.setattr(prompts, "LOG", tmp_path / "runs.log")
    monkeypatch.setattr(prompts, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(prompts, "_frozen_id", lambda: "frz123456789")
    monkeypatch.setattr(prompts.freeze, "FREEZE_FILE", tmp_path / "FREEZE.json")
    (tmp_path / "FREEZE.json").write_text(json.dumps({"components": {"engine_source": "e" * 64}}), encoding="utf-8")
    return tmp_path


def test_build_writes_data_and_a_manifest_tied_to_the_frozen_engine(sandbox):
    manifest = prompts.build()
    assert manifest["counts"] == {"records": 3, "with_person": 2, "without_person": 1, "person_mentions": 2,
                                  "single_word_person_mentions": 0, "by_source": {"author": 2, "user": 1},
                                  "person_names_in_both_sources": 0}
    assert manifest["frozen_engine"]["freeze_id"] == "frz123456789"
    assert manifest["data"]["prompts.jsonl"] == prompts._sha256(prompts.DATA)
    assert "NOT representative" in manifest["composition_note"] and manifest["status"] == "built, not yet scored"


def test_rebuilding_before_any_run_is_allowed_for_example_after_the_owner_adds_prompts(sandbox):
    prompts.build()
    prompts.SOURCES["user"].write_text("Call [[Bo Chen]]\n---\nAnd [[Cy Dee]]\n", encoding="utf-8")
    assert prompts.build()["counts"]["records"] == 4


def test_run_requires_the_final_flag_and_a_manifest(sandbox):
    with pytest.raises(SystemExit, match="--final"):
        prompts.guard_run(final=False, again=False)
    with pytest.raises(SystemExit, match="no manifest"):
        prompts.guard_run(final=True, again=False)


def test_run_is_refused_if_the_data_or_a_source_file_changed_after_the_manifest(sandbox):
    prompts.build()
    prompts.SOURCES["user"].write_text("Call [[Someone Else]]\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="user.txt changed"):
        prompts.guard_run(final=True, again=False)
    prompts.build()
    prompts.DATA.write_text(prompts.DATA.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="prompts.jsonl changed"):
        prompts.guard_run(final=True, again=False)


def test_run_is_refused_if_the_engine_freeze_differs_from_the_manifest(sandbox, monkeypatch):
    prompts.build()
    monkeypatch.setattr(prompts, "_frozen_id", lambda: "different0000")
    with pytest.raises(SystemExit, match="different frozen engine"):
        prompts.guard_run(final=True, again=False)


@pytest.fixture
def stubbed_run(sandbox, monkeypatch):
    import evaluation.runner as runner

    monkeypatch.setattr(runner, "build_variants", lambda: [])
    monkeypatch.setattr(runner, "run_set", lambda *a, **k: {"variants": {}})
    monkeypatch.setattr(prompts, "render", lambda manifest, result: "md")
    prompts.build()
    return sandbox


def log_status(sandbox):
    return [line.rsplit("status=", 1)[1] for line in (sandbox / "runs.log").read_text(encoding="utf-8").splitlines()]


def test_a_successful_run_logs_started_then_ok_writes_results_and_marks_the_manifest(stubbed_run):
    prompts.run(final=True, again=False, iterations=10)
    assert log_status(stubbed_run) == ["started", "ok"]
    assert (stubbed_run / "results" / "prompts_final.json").exists() and (stubbed_run / "results" / "prompts_final.md").exists()
    assert json.loads((stubbed_run / "MANIFEST.json").read_text(encoding="utf-8"))["status"] == "scored"


def test_a_second_run_is_refused_and_so_is_a_rebuild(stubbed_run):
    prompts.run(final=True, again=False, iterations=10)
    with pytest.raises(SystemExit, match="already been scored"):
        prompts.guard_run(final=True, again=False)
    with pytest.raises(SystemExit, match="final and cannot be rebuilt"):
        prompts.build()


def test_an_intentional_repeat_is_allowed_and_logged(stubbed_run):
    prompts.run(final=True, again=False, iterations=10)
    prompts.run(final=True, again=True, iterations=10)
    lines = (stubbed_run / "runs.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4 and "again=True" in lines[2]


def test_a_crash_during_scoring_is_logged_before_and_after_and_blocks_a_silent_retry(stubbed_run, monkeypatch):
    import evaluation.runner as runner

    def boom(*args, **kwargs):
        raise RuntimeError("scoring failed")

    monkeypatch.setattr(runner, "run_set", boom)
    with pytest.raises(RuntimeError):
        prompts.run(final=True, again=False, iterations=10)
    assert log_status(stubbed_run) == ["started", "failed"]
    with pytest.raises(SystemExit, match="already been scored"):
        prompts.guard_run(final=True, again=False)


def test_the_frozen_original_state_is_not_affected_by_this_directory():
    """The prompt files live under evaluation/prompts/, which the existing freeze does not cover."""
    from evaluation import freeze

    covered = {p.name for p in freeze.ROOT.glob("*.py")} | {p.name for p in (freeze.ROOT / "data").glob("*.jsonl")}
    assert "prompts.jsonl" not in covered and "parse.py" not in covered
