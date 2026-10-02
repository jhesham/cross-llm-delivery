"""v0.4.0 R06: late network errors are final even after long output."""
import subprocess

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.validate import _pytest


def _git(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout if p.returncode == 0 else p.stdout + p.stderr


@pytest.fixture
def repo(tmp_path):
    for a in (["init", "-q"], ["config", "user.email", "n@n"], ["config", "user.name", "n"],
              ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git", *a], cwd=tmp_path, check=True)
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return None\n")
    (tmp_path / "test_calc.py").write_text("from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "b"], cwd=tmp_path, check=True)
    return tmp_path


class LongThenNetwork:
    """Retained full output lives outside the repo, like CLD's process capture files."""
    def __init__(self, outdir, stderr_text, keep_files=True):
        self.calls = 0
        self.out, self.err = outdir / "stdout.bin", outdir / "stderr.bin"
        self.out.write_text("x" * 5000)
        self.err.write_text(stderr_text)
        if not keep_files:
            self.out.unlink(); self.err.unlink()

    def run(self, task, workdir, feedback=None):
        self.calls += 1
        log = ("x" * 5000)[:4000]
        return ExecutorResult(ok=False, diff="", raw_log=log, process={
            "error": "nonzero_exit", "stdout_path": str(self.out), "stderr_path": str(self.err)})


def _deliver(repo, executor):
    from cld.orchestrator import deliver_slice
    return deliver_slice(SliceTask("s", "b", ["calc.py"], "test_calc.py"), executor=executor,
                         judge_fn=judge, workdir=str(repo), git_runner=_git, test_runner=_pytest,
                         model="codex:gpt-x@low")


def test_late_stderr_network_error_is_final(repo, tmp_path_factory):
    executor = LongThenNetwork(tmp_path_factory.mktemp("out"), "Error: getaddrinfo ENOTFOUND api.openai.com")
    result = _deliver(repo, executor)
    assert executor.calls == 1 and result.final_error == "network_unavailable"


def test_missing_retained_files_fall_back_to_raw_log(repo, tmp_path_factory):
    executor = LongThenNetwork(tmp_path_factory.mktemp("out"), "ignored", keep_files=False)
    result = _deliver(repo, executor)
    assert executor.calls == 3 and result.final_error is None


def test_successful_dispatch_is_never_reclassified(repo, tmp_path_factory):
    outdir = tmp_path_factory.mktemp("out")
    (outdir / "stderr.bin").write_text("retrying after getaddrinfo ENOTFOUND ... recovered")

    class Fixes:
        calls = 0
        def run(self, task, workdir, feedback=None):
            self.calls += 1
            from pathlib import Path
            Path(workdir, "calc.py").write_text("def add(a, b):\n    return a + b\n")
            return ExecutorResult(ok=True, diff="", raw_log="ok",
                                  process={"stderr_path": str(outdir / "stderr.bin")})

    result = _deliver(repo, Fixes())
    assert result.final_error is None
