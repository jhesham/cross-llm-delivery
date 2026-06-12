"""validate_model — evidence-backed headless validation harness.

Spins a throwaway real-git repo with a trivial known-answer slice (add(a,b)), dispatches
it to the model via the given executor, runs the REAL acceptance test as judge, and
promotes headless_status: pass->proven, fail->known-bad, executor-error->untested.

Uses the real-git integration harness (no live LLM — fake pass/fail executors).
"""

from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.validate import ValidationResult, validate_model
from tests.integration.harness import real_git_runner

pytestmark = pytest.mark.integration


class _PassExec:
    """Writes calc.py that satisfies the trivial known-answer test."""

    def run(self, task, workdir, feedback=None):
        (Path(workdir) / "calc.py").write_text(
            "def add(a, b):\n    return a + b\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        return ExecutorResult(ok=True, diff="+x", files_changed=["calc.py"], raw_log="")


class _FailExec:
    """Writes WRONG code so the acceptance test fails."""

    def run(self, task, workdir, feedback=None):
        (Path(workdir) / "calc.py").write_text(
            "def add(a, b):\n    return 0\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        return ExecutorResult(ok=True, diff="+x", files_changed=["calc.py"], raw_log="")


class _BoomExec:
    """Executor that raises — should yield 'untested', not a model verdict."""

    def run(self, task, workdir, feedback=None):
        raise RuntimeError("CLI not installed")


def test_validate_promotes_to_proven_on_pass(tmp_path):
    res = validate_model("opencode/x", executor=_PassExec(),
                         git_runner=real_git_runner, base_dir=str(tmp_path))
    assert isinstance(res, ValidationResult)
    assert res.passed is True
    assert res.status == "proven"


def test_validate_marks_known_bad_on_fail(tmp_path):
    res = validate_model("opencode/x", executor=_FailExec(),
                         git_runner=real_git_runner, base_dir=str(tmp_path))
    assert res.passed is False
    assert res.status == "known-bad"


def test_validate_executor_error_is_untested(tmp_path):
    res = validate_model("opencode/x", executor=_BoomExec(),
                         git_runner=real_git_runner, base_dir=str(tmp_path))
    assert res.passed is False
    assert res.status == "untested"
