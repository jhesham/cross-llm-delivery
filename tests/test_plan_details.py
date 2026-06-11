from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import PlanResult, SliceDetail, run_plan_parallel


def test_planresult_has_details_map():
    r = PlanResult()
    assert r.details == {}  # new field, default empty


def test_run_plan_parallel_records_per_slice_detail(tmp_path):
    led = Ledger(str(tmp_path / "l.json"))

    class Ex:
        def run(self, task, workdir, feedback=None):
            return ExecutorResult(ok=True, diff="+a\n+b\n", files_changed=["src/x.py"],
                                  token_usage={"output": 12}, raw_log="1 passed in 0.1s")

    def judge(files_changed, allowed, run_tests):
        from cld.judge import judge as j
        return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)

    slices = [SliceTask(id="A", brief="b", files=["src/x.py"], acceptance_test_path="t.py")]
    res = run_plan_parallel(slices, led, executor=Ex(), judge_fn=judge, max_workers=1)
    d = res.details["A"]
    assert isinstance(d, SliceDetail)
    assert d.status == "completed"
    assert d.files_changed == ["src/x.py"]
    assert d.attempts == 1
    assert d.diff_lines == 2  # two added lines in the diff
