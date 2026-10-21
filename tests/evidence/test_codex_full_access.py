"""v0.5 Task 12: investigate slices run Codex with full access inside a worktree, keeping the code role."""
import inspect

import pytest

from cld.executors.base import SliceTask
from tests.evidence._lazy import resolve
from tests.test_t16_codex_adapter import FakeCodexRunner, repo  # noqa: F401

C = "cld_providers.codex.contract"


def _supports():
    return "full_access" in inspect.signature(resolve(C, "build_invocation")).parameters


def test_full_access_keeps_code_role_and_git_root(tmp_path):
    assert _supports(), "build_invocation(full_access=...) not implemented"
    (tmp_path / ".git").mkdir()
    call = resolve(C, "build_invocation")("gpt-example", tmp_path, "implement the slice", full_access=True)
    assert call.argv[call.argv.index("--sandbox") + 1] == "danger-full-access"
    assert "Do not invoke CLD" in call.stdin and "evidence executor" not in call.stdin.lower()


def test_full_access_still_requires_git_root(tmp_path):
    assert _supports(), "build_invocation(full_access=...) not implemented"
    with pytest.raises(resolve(C, "CodexContractError")):
        resolve(C, "build_invocation")("gpt-example", tmp_path, "p", full_access=True)


def _exec_sandbox(runner):
    argv = [a for a, _, _ in runner.calls if a[:2] == ["codex", "exec"] and "--sandbox" in a][0]
    return argv[argv.index("--sandbox") + 1]


def test_evidence_executor_run_uses_full_access(repo):
    from cld_providers.codex.provider import CodexExecutor
    assert _supports(), "build_invocation(full_access=...) not implemented"
    runner = FakeCodexRunner(write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    CodexExecutor(model="gpt-example", runner=runner, evidence=True).run(
        SliceTask("A", "Make VALUE 2", ["value.py"], "test_value.py"), repo)
    assert _exec_sandbox(runner) == "danger-full-access"


def test_default_executor_run_unchanged(repo):
    from cld_providers.codex.provider import CodexExecutor
    runner = FakeCodexRunner(write=lambda cwd: (cwd / "value.py").write_text("VALUE = 2\n", encoding="utf-8"))
    CodexExecutor(model="gpt-example", runner=runner).run(
        SliceTask("A", "Make VALUE 2", ["value.py"], "test_value.py"), repo)
    assert _exec_sandbox(runner) == "workspace-write"
