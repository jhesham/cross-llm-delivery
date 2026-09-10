"""Independent T02 outcome assertions against real Git objects and real pytest."""
from pathlib import Path
import os
from types import SimpleNamespace

import pytest

from cld.candidate import CandidateVerifier
from cld.executors._capture import CaptureError, capture_diff
from cld.executors.base import ExecutorResult
from cld.judge import judge
from cld.orchestrator import deliver_slice
from tests.integration.harness import FileCreatingExecutor, real_git_runner
from tests.integration.test_review_regressions import (
    BODY, acceptance, checked_git, delivery_repo, run, task,
)

pytestmark = pytest.mark.integration


class Writer:
    def __init__(self, write, result=None):
        self.write = write
        self.result = result if result is not None else ExecutorResult(True, "", [])
        self.calls = 0

    def run(self, t, wd, feedback=None):
        self.calls += 1
        self.write(t, Path(wd))
        return self.result


def deliver(repo, executor, **kwargs):
    return deliver_slice(task(), executor=executor, judge_fn=judge, workdir=str(repo),
                         git_runner=real_git_runner, test_runner=acceptance,
                         max_retries=0, **kwargs)


@pytest.mark.parametrize("commit", [False, True])
def test_spoofed_empty_report_records_actual_candidate(delivery_repo, commit):
    def write(t, wd):
        (wd / "implementation.py").write_text(BODY)
        if commit:
            checked_git(["add", "-A"], wd)
            checked_git(["commit", "-qm", "executor commit"], wd)
    base = checked_git(["rev-parse", "HEAD"], delivery_repo).strip()
    result = deliver(delivery_repo, Writer(write))
    assert result.accepted, result.final
    assert result.files_changed == ["implementation.py"]
    assert result.candidate.base == base
    assert checked_git(["show", f"{result.candidate.tree}:implementation.py"], delivery_repo) == BODY
    assert len(result.candidate.tests_fingerprint) == 64


@pytest.mark.parametrize("name", ["test_acceptance.py", "conftest.py", "tests/data.txt"])
def test_committed_test_tampering_rejected_even_when_allowed(delivery_repo, name):
    t = task()
    t.files.append(name)
    def write(t, wd):
        (wd / "implementation.py").write_text(BODY)
        path = wd / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("def test_fake(): assert True\n")
        checked_git(["add", "-A"], wd)
        checked_git(["commit", "-qm", "tamper"], wd)
    result = run(delivery_repo, executor=Writer(write), slices=[t])
    assert result.failed == ["A"]
    assert "protected" in " ".join(result.details["A"].failing_tests).lower()


@pytest.mark.parametrize("completion", [ExecutorResult(False, ""), None, {},
                                        SimpleNamespace(ok=True), ExecutorResult(1, "")])
def test_failed_or_malformed_completion_cannot_accept_allowed_writes(delivery_repo, completion):
    ex = Writer(lambda t, wd: (wd / "implementation.py").write_text(BODY))
    ex.result = completion
    result = deliver(delivery_repo, ex)
    assert not result.accepted


@pytest.mark.parametrize("location", ["snapshot", "executor"])
@pytest.mark.parametrize("name", ["implementation.py", "injected.py", "test_acceptance.py"])
def test_test_time_mutations_rejected(delivery_repo, location, name):
    seen = []
    def tests(wd, selector):
        seen.append(wd)
        output = acceptance(wd, selector)
        if len(seen) == 2:  # baseline preflight must stay unchanged
            destination = Path(wd) if location == "snapshot" else delivery_repo
            (destination / name).write_text("# modified after the tests\n")
        return output
    result = deliver_slice(task(), executor=FileCreatingExecutor(contents={"implementation.py": BODY}),
        judge_fn=judge, workdir=str(delivery_repo), git_runner=real_git_runner,
        test_runner=tests, max_retries=0)
    assert len(seen) == 2 and all(Path(wd) != delivery_repo for wd in seen)
    assert not result.accepted


@pytest.mark.parametrize("selector", ["missing.py", "../test_acceptance.py", "C:/escape.py",
                                      "test_acceptance.py --override-ini=x"])
def test_invalid_acceptance_does_not_dispatch(delivery_repo, selector):
    t = task()
    t.acceptance_test_path = selector
    ex = Writer(lambda t, wd: None)
    result = run(delivery_repo, executor=ex, slices=[t])
    assert ex.calls == 0 and result.failed == ["A"]


@pytest.mark.parametrize("body", ["import absent_t02_module\n", "def broken(:\n", "# no tests\n",
                                  "def test_error(): raise RuntimeError('broken setup')\n"])
def test_invalid_baseline_is_not_red_acceptance(delivery_repo, body):
    (delivery_repo / "test_acceptance.py").write_text(body)
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "invalid acceptance"], delivery_repo)
    ex = Writer(lambda t, wd: None)
    result = run(delivery_repo, executor=ex)
    assert ex.calls == 0 and result.failed == ["A"]


@pytest.mark.parametrize("permit", [False, True])
def test_no_change_requires_explicit_passing_baseline_policy(delivery_repo, permit):
    (delivery_repo / "implementation.py").write_text(BODY)
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "already satisfied"], delivery_repo)
    t = task()
    t.allow_already_satisfied = permit
    result = deliver_slice(t, executor=Writer(lambda t, wd: None), judge_fn=judge,
        workdir=str(delivery_repo), git_runner=real_git_runner, test_runner=acceptance, max_retries=0)
    assert result.accepted is permit


def test_source_fixture_input_is_protected(delivery_repo):
    (delivery_repo / "fixture.json").write_text('{}')
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "fixture"], delivery_repo)
    t = task()
    t.files.append("fixture.json")
    t.protected_inputs = ["fixture.json"]
    result = run(delivery_repo, slices=[t], executor=Writer(
        lambda t, wd: (wd / "fixture.json").write_text('{"tampered":true}')))
    assert result.failed == ["A"]


def test_executor_cannot_rewrite_contract(delivery_repo):
    def write(t, wd):
        t.acceptance_test_path = "missing.py"
        t.files.append("forbidden.py")
        (wd / "forbidden.py").write_text("bad")
        (wd / "implementation.py").write_text(BODY)
    result = run(delivery_repo, executor=Writer(write))
    assert result.failed == ["A"]


def test_collection_rejects_edits_after_successful_judge(delivery_repo):
    result = deliver(delivery_repo, Writer(lambda t, wd: (wd / "implementation.py").write_text(BODY)))
    assert result.accepted
    (delivery_repo / "implementation.py").write_text("VALUE = 13\n")
    with pytest.raises(CaptureError, match="differs"):
        CandidateVerifier(real_git_runner, str(delivery_repo), task(),
                          base=result.candidate.base).prepare_collection(result.candidate)


def test_capture_complete_git_changes_and_literal_names(delivery_repo):
    names = ["binary.bin", "delete.txt", "old.txt", "mode.sh", "space ü.txt", "ignored.dat", "staged.txt"]
    if os.name != "nt":
        names.extend(["line\nbreak.txt", "carriage\rreturn.txt", "[literal]*.txt"])
    for name in ["binary.bin", "delete.txt", "old.txt", "mode.sh", "staged.txt"]:
        (delivery_repo / name).write_bytes(b"old\0bytes" if name == "binary.bin" else b"old\n")
    (delivery_repo / ".gitignore").write_text("ignored.dat\n")
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "all change types baseline"], delivery_repo)
    checked_git(["config", "core.filemode", "true"], delivery_repo)
    t = task()
    t.files = names + ["renamed.txt"]
    verifier = CandidateVerifier(real_git_runner, str(delivery_repo), t)
    (delivery_repo / "binary.bin").write_bytes(b"new\0binary\xff")
    (delivery_repo / "delete.txt").unlink()
    checked_git(["mv", "old.txt", "renamed.txt"], delivery_repo)
    (delivery_repo / "space ü.txt").write_text("new")
    (delivery_repo / "ignored.dat").write_text("ignored source still captured")
    (delivery_repo / "staged.txt").write_text("stage first")
    checked_git(["add", "staged.txt"], delivery_repo)
    (delivery_repo / "staged.txt").write_text("final unstaged")
    # POSIX mode changes are preserved in the worktree. On Windows, Git's
    # index-only executable-bit operation is covered separately below.
    if os.name != "nt":
        (delivery_repo / "mode.sh").chmod(0o755)
        (delivery_repo / "line\nbreak.txt").write_text("newline name")
        (delivery_repo / "carriage\rreturn.txt").write_text("carriage return name")
        (delivery_repo / "[literal]*.txt").write_text("literal glob characters")
    else:
        names.remove("mode.sh")
    candidate = verifier.capture()
    assert set(candidate.files_changed) == set(names + ["renamed.txt"])
    assert "GIT binary patch" in candidate.diff
    assert checked_git(["show", f"{candidate.tree}:staged.txt"], delivery_repo) == "final unstaged"
    # Provider capture also preserves literal names rather than splitlines/strip.
    _, changed = capture_diff(real_git_runner, str(delivery_repo), base=verifier.base)
    assert "space ü.txt" in changed


def test_symlink_candidate_is_rejected_before_tests(delivery_repo):
    verifier = CandidateVerifier(real_git_runner, str(delivery_repo), task())
    try:
        (delivery_repo / "escape").symlink_to(delivery_repo.parent, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not grant symlink creation")
    with pytest.raises(CaptureError, match="Symlink"):
        verifier.capture()


def test_index_mode_change_is_captured(delivery_repo):
    checked_git(["config", "core.filemode", "false"], delivery_repo)
    verifier = CandidateVerifier(real_git_runner, str(delivery_repo), task())
    checked_git(["update-index", "--chmod=+x", "implementation.py"], delivery_repo)
    candidate = verifier.capture()
    assert candidate.files_changed == ("implementation.py",)
    assert "new mode 100755" in candidate.diff


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_index_flags_cannot_hide_test_tampering(delivery_repo, flag):
    verifier = CandidateVerifier(real_git_runner, str(delivery_repo), task())
    checked_git(["update-index", flag, "test_acceptance.py"], delivery_repo)
    (delivery_repo / "test_acceptance.py").write_text("def test_fake(): assert True\n")
    with pytest.raises(CaptureError, match="Protected"):
        verifier.capture()


def test_mixed_assertion_and_runtime_error_baseline_is_rejected(delivery_repo):
    (delivery_repo / "test_acceptance.py").write_text(
        "def test_assert(): assert False\ndef test_error(): raise RuntimeError('bad setup')\n")
    checked_git(["add", "-A"], delivery_repo)
    checked_git(["commit", "-qm", "mixed errors"], delivery_repo)
    ex = Writer(lambda t, wd: None)
    result = run(delivery_repo, executor=ex)
    assert ex.calls == 0 and result.failed == ["A"]


def test_skipped_acceptance_is_not_success(delivery_repo):
    def write(t, wd):
        (wd / "implementation.py").write_text("import pytest\npytest.skip('bypass', allow_module_level=True)\n")
    result = deliver(delivery_repo, Writer(write))
    assert not result.accepted
