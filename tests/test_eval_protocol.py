"""The held-out test split must be hard to use by accident: explicit flag, logged BEFORE use, refused on repeat."""
import pytest

from evaluation import __main__ as cli


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RESULTS", tmp_path)
    monkeypatch.setattr(cli.freeze, "differences", lambda: [])  # these tests are about logging; freezing has its own file
    return tmp_path


def log_lines(results_dir):
    return (results_dir / "test_runs.log").read_text(encoding="utf-8").splitlines()


def test_test_split_requires_the_final_flag(results_dir):
    with pytest.raises(SystemExit, match="--final"):
        cli.guard_test_split(final=False, again=False)


def test_an_event_records_hashes_and_status(results_dir):
    cli.log_test_event(again=False, status="started")
    line = log_lines(results_dir)[0]
    assert f"code={cli.code_hash()}" in line and f"data={cli.data_hash('test')}" in line
    assert "again=False" in line and line.endswith("status=started")


def test_repeating_on_unchanged_engine_source_is_refused(results_dir):
    cli.guard_test_split(final=True, again=False)
    cli.log_test_event(again=False, status="ok")
    with pytest.raises(SystemExit, match="already evaluated"):
        cli.guard_test_split(final=True, again=False)


def test_a_started_but_never_finished_attempt_still_counts_as_a_use(results_dir):
    cli.log_test_event(again=False, status="started")  # e.g. the process was killed mid-run
    with pytest.raises(SystemExit, match="already evaluated"):
        cli.guard_test_split(final=True, again=False)


def test_an_intentional_repeat_is_allowed_but_is_itself_logged(results_dir):
    cli.log_test_event(again=False, status="ok")
    cli.guard_test_split(final=True, again=True)
    cli.log_test_event(again=True, status="ok")
    assert len(log_lines(results_dir)) == 2 and "again=True" in log_lines(results_dir)[1]


def test_a_different_engine_source_hash_is_a_new_version_and_is_allowed(results_dir, monkeypatch):
    cli.log_test_event(again=False, status="ok")
    monkeypatch.setattr(cli, "code_hash", lambda: "different0000000")
    cli.guard_test_split(final=True, again=False)


def test_code_hash_changes_when_engine_source_changes(tmp_path, monkeypatch):
    src = tmp_path / "pii_engine"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(cli, "SRC", src)
    before = cli.code_hash()
    (src / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert cli.code_hash() != before


# ---- the whole flow, with the heavy parts replaced ----------------------------------------------------


@pytest.fixture
def stubbed(results_dir, monkeypatch):
    monkeypatch.setattr(cli, "build_variants", lambda: [])
    monkeypatch.setattr(cli, "markdown", lambda report: "md")
    return results_dir


def test_a_successful_test_run_logs_started_then_ok(stubbed, monkeypatch):
    monkeypatch.setattr(cli, "run_set", lambda *a, **k: {})
    assert cli.main(["--split", "test", "--final"]) == 0
    assert [line.rsplit("status=", 1)[1] for line in log_lines(stubbed)] == ["started", "ok"]
    assert (stubbed / "test.json").exists()


def test_a_crash_during_scoring_is_logged_before_and_after_and_blocks_a_silent_retry(stubbed, monkeypatch):
    """Review finding: the use used to be logged only at the end, so a failed run left no trace."""
    def boom(*args, **kwargs):
        raise RuntimeError("scoring failed")

    monkeypatch.setattr(cli, "run_set", boom)
    with pytest.raises(RuntimeError):
        cli.main(["--split", "test", "--final"])
    assert [line.rsplit("status=", 1)[1] for line in log_lines(stubbed)] == ["started", "failed"]
    with pytest.raises(SystemExit, match="already evaluated"):
        cli.main(["--split", "test", "--final"])


def test_a_failure_while_writing_the_report_is_also_logged(stubbed, monkeypatch):
    monkeypatch.setattr(cli, "run_set", lambda *a, **k: {})

    def broken_markdown(report):
        raise OSError("disk full")

    monkeypatch.setattr(cli, "markdown", broken_markdown)
    with pytest.raises(OSError):
        cli.main(["--split", "test", "--final"])
    assert [line.rsplit("status=", 1)[1] for line in log_lines(stubbed)] == ["started", "failed"]


def test_a_keyboard_interrupt_counts_as_a_failed_use(stubbed, monkeypatch):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_set", interrupted)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["--split", "test", "--final"])
    assert log_lines(stubbed)[-1].endswith("status=failed")


def test_dev_runs_never_write_a_test_log(stubbed, monkeypatch):
    monkeypatch.setattr(cli, "run_set", lambda *a, **k: {})
    assert cli.main(["--split", "dev", "--tag", "unit"]) == 0
    assert not (stubbed / "test_runs.log").exists() and (stubbed / "dev_unit.json").exists()


def test_the_test_split_is_refused_without_final_and_logs_nothing(stubbed):
    with pytest.raises(SystemExit):
        cli.main(["--split", "test"])
    assert not (stubbed / "test_runs.log").exists()
