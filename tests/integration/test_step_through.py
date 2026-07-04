"""End-to-end: drive a 2-layer plan via next_pending_layer + run_plan_parallel against REAL git,
asserting the ledger advances layer-by-layer, slices land in their branches, and the summary
carries no raw output."""
from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import next_pending_layer, run_plan_parallel
from cld.summary import summarize_layer
from tests.integration.harness import init_repo, real_git_runner

pytestmark = pytest.mark.integration


class RealFileExecutor:
    def run(self, task, workdir, feedback=None):
        for rel in task.files:
            p = Path(workdir) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {task.id}\n", encoding="utf-8")
        real_git_runner(["git", "add", "--intent-to-add", "-A"], str(workdir))
        _, names = real_git_runner(["git", "diff", "HEAD", "--name-only"], str(workdir))
        files = [ln.strip() for ln in names.splitlines() if ln.strip()]
        return ExecutorResult(ok=True, diff="+x\n", files_changed=files,
                              token_usage={}, raw_log="")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as j
    return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def _pass(workdir):
    return "1 passed in 0.0s"


def _slices():
    return [
        SliceTask(id="A", brief="b", files=["pkg/a.py"], acceptance_test_path="t.py"),
        SliceTask(id="B", brief="b", files=["pkg/b.py"], acceptance_test_path="t.py", deps=["A"]),
    ]


def _run_one_layer(slices, ledger, repo):
    sel = next_pending_layer(slices, ledger)
    if sel is None:
        return None
    idx, layer_ids, total = sel
    layer = [s for s in slices if s.id in layer_ids]
    res = run_plan_parallel(layer, ledger, executor=RealFileExecutor(), judge_fn=_judge,
                            max_workers=2, repo_dir=repo, git_runner=real_git_runner,
                            test_runner=_pass)
    nxt = next_pending_layer(slices, ledger)
    summary = summarize_layer(res, layer_index=idx, total_layers=total,
                              next_layer=(nxt[1] if nxt else []))
    return res, summary


def test_step_through_two_layers(git_repo):
    repo = git_repo
    slices = _slices()
    ledger = Ledger(str(Path(repo) / ".cld-ledger.json"))

    # layer 0: A
    res0, sum0 = _run_one_layer(slices, ledger, repo)
    assert res0.completed == ["A"]
    assert "LAYER 1 of 2" in sum0
    assert "diff --git" not in sum0  # no raw output on the summary
    assert ledger.is_done("A") and not ledger.is_done("B")

    # layer 1: B (now unblocked)
    res1, sum1 = _run_one_layer(slices, ledger, repo)
    assert res1.completed == ["B"]
    assert "LAYER 2 of 2" in sum1
    assert ledger.is_done("B")

    # complete
    assert next_pending_layer(slices, ledger) is None

    # collected to branches
    def files_on(branch):
        _, out = real_git_runner(["git", "ls-tree", "-r", "--name-only", branch], repo)
        return set(x.strip() for x in out.splitlines() if x.strip())
    assert "pkg/a.py" in files_on("slice-A")
    assert "pkg/b.py" in files_on("slice-B")
