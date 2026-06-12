"""Evidence-backed headless validation: does a model actually build a trivial slice?

CLI-headless does NOT imply MODEL-headless (a model can run headless yet describe code
instead of writing files, stall, or be throttled). The only honest signal is OBSERVING a
model complete a real slice. This harness spins a throwaway real-git repo with a trivial
known-answer slice (`add(a, b)`), dispatches it to the model via the given executor, runs
the REAL acceptance test (scoped — the Bug B discipline) as the judge, and reports a
promotion: pass -> proven, fail -> known-bad, executor error -> untested.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cld.executors.base import SliceTask
from cld.judge import judge

_TEST_SRC = (
    "from calc import add\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n"
)


@dataclass
class ValidationResult:
    model: str
    passed: bool
    status: str          # "proven" | "known-bad" | "untested"
    attempts: int
    note: str = ""


def _pytest(workdir: str, test_path: str) -> str:
    """Run ONLY the slice's acceptance test in the repo (scoped — Bug B), with a
    timeout so a hung test cannot freeze validation."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-q"],
            cwd=workdir, capture_output=True, text=True, timeout=120,
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return "1 failed in 120s (timeout)"


def _init_repo(repo: str, git_runner) -> None:
    """Real git repo with the failing acceptance test committed (HEAD exists)."""
    Path(repo).mkdir(parents=True, exist_ok=True)
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "v@cld.test"],
        ["git", "config", "user.name", "cld-validate"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        git_runner(args, repo)
    (Path(repo) / "test_calc.py").write_text(_TEST_SRC, encoding="utf-8")
    git_runner(["git", "add", "-A"], repo)
    git_runner(["git", "commit", "-qm", "init"], repo)


def validate_model(model: str, *, executor, git_runner, base_dir: str) -> ValidationResult:
    repo = str(Path(base_dir) / "validate-repo")
    _init_repo(repo, git_runner)

    task = SliceTask(
        id="validate",
        brief="Implement add(a, b) returning a + b in calc.py.",
        files=["calc.py"],
        acceptance_test_path="test_calc.py",
    )
    try:
        result = executor.run(task, repo)
    except Exception as exc:  # executor blew up -> untested, not a model-failure verdict
        return ValidationResult(model, False, "untested", 0, note=f"executor error: {exc}")

    jr = judge(
        result.files_changed, task.files,
        run_tests=lambda: _pytest(repo, task.acceptance_test_path),
    )
    if jr.passed:
        return ValidationResult(model, True, "proven", 1)
    return ValidationResult(
        model, False, "known-bad", 1,
        note="; ".join(jr.failing_tests) or "acceptance test failed",
    )
