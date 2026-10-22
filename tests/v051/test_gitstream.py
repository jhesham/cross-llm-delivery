"""v0.5.1 GITSTREAM: Git stderr never corrupts NUL-delimited stdout, and is kept for diagnostics."""
import subprocess

import pytest

from tests.evidence._lazy import resolve
from tests.v051._red import must


def _fake_run(monkeypatch, returncode, stdout, stderr):
    from cld import cli

    def run(args, cwd=None, capture_output=None, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    monkeypatch.setattr(cli.subprocess, "run", run)
    return cli.git_runner


def _capture():
    return (resolve("cld.executors._capture", "checked"), resolve("cld.executors._capture", "nul_names"),
            resolve("cld.executors._capture", "CaptureError"))


def test_success_with_stderr_warning_parses_stdout_only(monkeypatch):
    runner = _fake_run(monkeypatch, 0, b"calc.py\0", b"warning: in the working copy of 'calc.py', LF will be replaced\n")
    checked, nul_names, _ = _capture()
    assert must(lambda: nul_names(checked(runner, ".", "diff", "--name-only", "-z"))) == ["calc.py"]


def test_success_keeps_stderr_for_diagnostics(monkeypatch):
    runner = _fake_run(monkeypatch, 0, b"calc.py\0", b"warning: noted\n")
    rc, output = runner(["git", "status"], ".")
    assert rc == 0 and output == "calc.py\0" and getattr(output, "stderr", None) == "warning: noted\n"


def test_incomplete_stdout_fails_closed_and_names_the_warning(monkeypatch):
    runner = _fake_run(monkeypatch, 0, b"calc.py", b"warning: could not open directory 'build/': Permission denied\n")
    checked, nul_names, CaptureError = _capture()
    with pytest.raises(CaptureError) as info:
        nul_names(checked(runner, ".", "ls-files", "-z"))
    assert "could not open directory" in str(info.value)


def test_nonzero_exit_reports_stderr(monkeypatch):
    runner = _fake_run(monkeypatch, 128, b"", b"fatal: not a git repository\n")
    checked, _, CaptureError = _capture()
    with pytest.raises(CaptureError) as info:
        checked(runner, ".", "ls-files", "-z")
    assert "not a git repository" in str(info.value)


def test_special_filenames_survive(monkeypatch):
    runner = _fake_run(monkeypatch, 0, "a b.py\0new\nline.py\0café.py\0".encode("utf-8"), b"warning\n")
    checked, nul_names, _ = _capture()
    assert must(lambda: nul_names(checked(runner, ".", "ls-files", "-z"))) == ["a b.py", "new\nline.py", "café.py"]


def _ignored_runner(warning):
    GitOutput = resolve("cld.executors._capture", "GitOutput")

    def runner(argv, cwd):
        if argv[1:3] == ["ls-files", "--others"]:
            return 0, GitOutput("", stderr=warning)
        if argv[1:2] == ["write-tree"]:
            return 0, GitOutput("0" * 40 + "\n")
        if argv[1:2] in (["ls-tree"], ["ls-files"]):
            return 0, GitOutput("")
        return 0, GitOutput("")
    return runner


def test_unreadable_noise_directory_is_tolerated(tmp_path):
    capture_tree = resolve("cld.candidate", "capture_tree")
    runner = must(_ignored_runner, "warning: could not open directory '.pytest_cache/': Permission denied\n")
    assert must(capture_tree, runner, str(tmp_path), "HEAD") == "0" * 40


def test_unreadable_source_directory_fails_closed(tmp_path):
    capture_tree = resolve("cld.candidate", "capture_tree")
    CaptureError = resolve("cld.executors._capture", "CaptureError")
    runner = must(_ignored_runner, "warning: could not open directory 'src/secret/': Permission denied\n")
    with pytest.raises(CaptureError) as info:
        capture_tree(runner, str(tmp_path), "HEAD")
    assert "src/secret" in str(info.value)


def test_real_git_warning_does_not_break_capture(tmp_path):
    """Real Windows/POSIX Git: core.autocrlf warnings on stderr must not reach the NUL parser."""
    from cld.cli import git_runner
    checked, nul_names, _ = _capture()
    for args in (["init", "-q"], ["config", "core.autocrlf", "true"], ["config", "core.safecrlf", "warn"],
                 ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_bytes(b"x = 1\n")
    subprocess.run(["git", "add", "calc.py"], cwd=tmp_path, check=True, capture_output=True)
    assert nul_names(checked(git_runner, str(tmp_path), "diff", "--cached", "--name-only", "-z")) == ["calc.py"]
