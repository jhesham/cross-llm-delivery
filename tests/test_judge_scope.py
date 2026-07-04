"""Bug B regression: the judge must run ONLY the slice's acceptance test, not the
whole repo suite. Running the whole suite (a) bills a paid LLM if the target repo's
tests call one (e.g. advisor's `claude -p`), and (b) lets an unrelated hang freeze
the build. deliver_slice must pass the slice's acceptance_test_path to test_runner."""
from cld.executors.base import ExecutorResult, SliceTask
from cld.orchestrator import deliver_slice


class _Ex:
    def run(self, task, workdir, feedback=None):
        return ExecutorResult(ok=True, diff="+x\n", files_changed=["src/a.py"],
                              raw_log="ignored")


def _judge(files_changed, allowed, run_tests):
    from cld.judge import judge as j
    return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)


def test_test_runner_receives_acceptance_path():
    seen = {}

    def runner(workdir, acceptance_test_path):
        seen["workdir"] = workdir
        seen["path"] = acceptance_test_path
        return "1 passed in 0.0s"

    task = SliceTask(id="A", brief="b", files=["src/a.py"],
                     acceptance_test_path="tests/test_a.py")
    res = deliver_slice(task, executor=_Ex(), judge_fn=_judge, max_retries=0,
                        workdir="/wt", test_runner=runner)
    assert res.accepted is True
    assert seen["workdir"] == "/wt"
    assert seen["path"] == "tests/test_a.py"  # the slice's test, NOT a whole-suite run


def test_legacy_one_arg_runner_still_works():
    # A runner that only accepts (workdir) must keep working (backward compat).
    def runner(workdir):
        return "1 passed in 0.0s"

    task = SliceTask(id="A", brief="b", files=["src/a.py"], acceptance_test_path="t.py")
    res = deliver_slice(task, executor=_Ex(), judge_fn=_judge, max_retries=0,
                        workdir="/wt", test_runner=runner)
    assert res.accepted is True
