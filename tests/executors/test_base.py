"""Acceptance tests for the executor interface (T2.1 contract).

These are authored by Claude (the architect) BEFORE implementation; the executor
must make them pass without editing this file.
"""

from dataclasses import fields
from pathlib import Path

from cld.executors.base import Executor, ExecutorResult, SliceTask


def test_slicetask_fields_and_construction():
    t = SliceTask(
        id="T2.1",
        brief="implement the thing",
        files=["src/cld/executors/base.py"],
        acceptance_test_path="tests/executors/test_base.py",
    )
    assert t.id == "T2.1"
    assert t.brief == "implement the thing"
    assert t.files == ["src/cld/executors/base.py"]
    assert t.acceptance_test_path == "tests/executors/test_base.py"
    # deps omitted -> defaults to empty list
    assert t.deps == []


def test_slicetask_deps_default_is_not_shared():
    a = SliceTask(id="a", brief="", files=[], acceptance_test_path="x")
    b = SliceTask(id="b", brief="", files=[], acceptance_test_path="x")
    a.deps.append("a-dep")
    # mutable default must use default_factory; instances must not share state
    assert b.deps == []


def test_slicetask_equality():
    kw = dict(id="z", brief="b", files=["f"], acceptance_test_path="p", deps=["d"])
    assert SliceTask(**kw) == SliceTask(**kw)


def test_executorresult_fields_and_defaults():
    r = ExecutorResult(ok=True, diff="--- a\n+++ b\n")
    assert r.ok is True
    assert r.diff == "--- a\n+++ b\n"
    # collection/log fields default to empty
    assert r.files_changed == []
    assert r.token_usage == {}
    assert r.raw_log == ""


def test_executorresult_defaults_not_shared():
    a = ExecutorResult(ok=True, diff="")
    b = ExecutorResult(ok=False, diff="")
    a.files_changed.append("x")
    a.token_usage["total"] = 1
    assert b.files_changed == []
    assert b.token_usage == {}


def test_executor_is_runtime_checkable_protocol():
    class FakeExecutor:
        def run(self, task: SliceTask, workdir: Path) -> ExecutorResult:
            return ExecutorResult(ok=True, diff="")

    class NotAnExecutor:
        pass

    assert isinstance(FakeExecutor(), Executor)
    assert not isinstance(NotAnExecutor(), Executor)


def test_executor_run_signature():
    # the Protocol must declare run(task, workdir) -> ExecutorResult
    run = Executor.run
    params = list(run.__annotations__) if hasattr(run, "__annotations__") else []
    # at minimum the return annotation should be ExecutorResult
    assert run.__annotations__.get("return") is ExecutorResult
    assert "task" in run.__annotations__
    assert "workdir" in run.__annotations__


def test_slicetask_has_optional_executor_field():
    t = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    assert t.executor is None  # defaults to None (use build default)
    t2 = SliceTask(id="T2", brief="b", files=["x"], acceptance_test_path="t.py",
                   executor="opencode:opencode/claude-sonnet-4-6")
    assert t2.executor == "opencode:opencode/claude-sonnet-4-6"


def test_slicetask_complexity_defaults_standard():
    t = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    assert t.complexity == "standard"
    t2 = SliceTask(id="T2", brief="b", files=["x"], acceptance_test_path="t.py", complexity="complex")
    assert t2.complexity == "complex"


