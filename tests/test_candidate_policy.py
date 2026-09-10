import pytest

from cld.candidate import acceptance_args, safe_path
from cld.executors._capture import CaptureError
from cld.executors.base import ExecutorResult, SliceTask
from cld.judge import judge
from cld.ledger import Ledger
from cld.orchestrator import deliver_slice, run_plan_parallel
from cld.plan.slice import load_slices, slices_to_markdown


@pytest.mark.parametrize("path", ["../escape", "/root", "C:/root", "a/../b", "a\\b",
                                  ".git/config", "a/.GIT/config", "a//b", "a/./b", "x\0y", ":(glob)*"])
def test_path_escape_and_pathspec_magic_rejected(path):
    with pytest.raises(CaptureError):
        safe_path(path)


def test_literal_acceptance_path_and_scoped_selector():
    assert acceptance_args("tests/a ü.py::test_it") == ["tests/a ü.py::test_it"]
    assert acceptance_args('"tests/a ü.py" -k "one or two"') == ["tests/a ü.py", "-k", "one or two"]
    with pytest.raises(CaptureError):
        acceptance_args('t.py -k "one" --override-ini=x')


def test_plan_roundtrip_protected_inputs_and_noop_policy():
    t = SliceTask("A", "brief", ["src.py"], "tests/test_src.py",
                  protected_inputs=["data/fixture.json"], allow_already_satisfied=True)
    assert load_slices(slices_to_markdown([t])) == [t]
    with pytest.raises(ValueError):
        load_slices("## SLICE: A\nallow_already_satisfied: maybe\n")


def test_missing_verification_boundary_cannot_dispatch(tmp_path):
    class Ex:
        calls = 0
        def run(self, t, wd):
            self.calls += 1
            return ExecutorResult(True, "", raw_log="1 passed")
    ex = Ex()
    t = SliceTask("A", "brief", [], "t.py")
    with pytest.raises(CaptureError, match="git_runner"):
        deliver_slice(t, executor=ex, judge_fn=judge)
    with pytest.raises(CaptureError, match="repo_dir"):
        run_plan_parallel([t], Ledger(str(tmp_path / "ledger")), executor=ex, judge_fn=judge)
    with pytest.raises(CaptureError, match="Simulation"):
        deliver_slice(t, executor=ex, judge_fn=judge, simulation=True, git_runner=lambda *a: (0, ""))
    assert ex.calls == 0
