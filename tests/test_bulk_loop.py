"""Acceptance tests for the BULK single-slice-loop slice (T3.1 + T3.2 + T3.4).

Authored by Claude before executor dispatch. Spans three modules:
plan/slice.py (loader), worktree.py (git CM), orchestrator.py (deliver_slice).
All external effects are injected — no live git/subprocess in tests.
"""

from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import JudgeResult
from cld.orchestrator import DeliverResult, deliver_slice
from cld.plan.slice import load_slices, slices_to_markdown
from cld.worktree import worktree


PLAN_MD = """## SLICE: T1
brief: Do the first thing
files: src/a.py, tests/test_a.py
acceptance_test_path: tests/test_a.py
deps:

## SLICE: T2
brief: Do the second thing
files: src/b.py
acceptance_test_path: tests/test_b.py
deps: T1
"""


# ---- Module 1: plan/slice.py ----

def test_load_slices_parses_all():
    slices = load_slices(PLAN_MD)
    assert [s.id for s in slices] == ["T1", "T2"]
    assert slices[0].brief == "Do the first thing"
    assert slices[0].files == ["src/a.py", "tests/test_a.py"]
    assert slices[0].acceptance_test_path == "tests/test_a.py"
    assert slices[0].deps == []
    assert slices[1].deps == ["T1"]
    assert slices[1].files == ["src/b.py"]


def test_load_slices_empty():
    assert load_slices("") == []


def test_load_slices_tolerates_unknown_lines():
    md = "## SLICE: X\nbrief: hi\nrandom noise line\nfiles: a.py\nacceptance_test_path: t.py\ndeps:\n"
    slices = load_slices(md)
    assert len(slices) == 1
    assert slices[0].id == "X"
    assert slices[0].files == ["a.py"]


def test_slices_roundtrip():
    original = load_slices(PLAN_MD)
    md = slices_to_markdown(original)
    again = load_slices(md)
    assert [(s.id, s.brief, s.files, s.deps) for s in original] == [
        (s.id, s.brief, s.files, s.deps) for s in again
    ]


# ---- Module 2: worktree.py ----

class FakeRunner:
    """Records git commands; returns a configurable (rc, output)."""

    def __init__(self, rc=0, output=""):
        self.calls = []
        self.rc = rc
        self.output = output

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        return (self.rc, self.output)


def test_worktree_adds_and_removes():
    runner = FakeRunner()
    with worktree("/repo", "feat-x", runner=runner) as path:
        assert isinstance(path, str)
        assert path  # non-empty
    # first call adds, last call removes
    add_args = runner.calls[0][0]
    remove_args = runner.calls[-1][0]
    assert "add" in add_args
    assert "-b" in add_args and "feat-x" in add_args
    assert "remove" in remove_args


def test_worktree_removes_on_exception():
    runner = FakeRunner()
    try:
        with worktree("/repo", "feat-y", runner=runner):
            raise ValueError("boom")
    except ValueError:
        pass
    assert any("remove" in c[0] for c in runner.calls)


def test_worktree_raises_on_add_failure_without_remove():
    runner = FakeRunner(rc=1, output="fatal: branch exists")
    try:
        with worktree("/repo", "dup", runner=runner):
            assert False, "should not enter body"
    except RuntimeError as e:
        assert "fatal" in str(e)
    # add failed → no remove attempted
    assert all("remove" not in c[0] for c in runner.calls)


# ---- Module 3: orchestrator.py ----

class FakeExecutor:
    """Executor protocol: returns a preset ExecutorResult."""

    def __init__(self, files_changed, raw_log):
        self._files = files_changed
        self._log = raw_log

    def run(self, task, workdir):
        return ExecutorResult(
            ok=True, diff="", files_changed=self._files, raw_log=self._log
        )


def _real_judge_fn(files_changed, allowed, run_tests):
    from cld.judge import judge as _judge
    return _judge(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def test_deliver_slice_accepts_on_clean_pass():
    task = SliceTask(id="T1", brief="b", files=["src/a.py"], acceptance_test_path="t.py")
    ex = FakeExecutor(files_changed=["src/a.py"], raw_log="3 passed in 0.1s")
    res = deliver_slice(task, executor=ex, judge_fn=_real_judge_fn, max_retries=2)
    assert isinstance(res, DeliverResult)
    assert res.accepted is True
    assert res.attempts == 1
    assert res.final.passed is True
    assert len(res.history) == 1


def test_deliver_slice_fails_after_retries():
    task = SliceTask(id="T2", brief="b", files=["src/b.py"], acceptance_test_path="t.py")
    ex = FakeExecutor(
        files_changed=["src/b.py"], raw_log="FAILED t.py::test_x\n1 failed in 0.1s"
    )
    res = deliver_slice(task, executor=ex, judge_fn=_real_judge_fn, max_retries=2)
    assert res.accepted is False
    assert res.attempts == 3  # max_retries + 1
    assert len(res.history) == 3
    assert res.final.passed is False


def test_deliver_slice_rejects_disallowed_edit():
    task = SliceTask(id="T3", brief="b", files=["src/c.py"], acceptance_test_path="t.py")
    ex = FakeExecutor(
        files_changed=["src/c.py", "secret.py"], raw_log="2 passed in 0.1s"
    )
    res = deliver_slice(task, executor=ex, judge_fn=_real_judge_fn, max_retries=1)
    assert res.accepted is False
    assert res.final.disallowed_edits == ["secret.py"]


def test_deliver_result_history_default_not_shared():
    a = DeliverResult(accepted=True, attempts=1, final=None)
    b = DeliverResult(accepted=True, attempts=1, final=None)
    a.history.append(JudgeResult(passed=True, tests_passed=1, tests_failed=0))
    assert b.history == []
