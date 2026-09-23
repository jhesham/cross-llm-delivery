"""The process must stop before recovery inspects and pins partial edits (R02)."""
import json
from pathlib import Path
import sys
import threading
import time

import pytest

from cld.executors.base import ExecutorResult
from cld.process import run_process, feedback
from tests.integration.test_review_regressions import BODY, delivery_repo, run, checked_git, task


@pytest.mark.parametrize("mode", ["timeout", "cancelled"])
def test_partial_process_work_retained_and_never_accepted(delivery_repo, mode):
    calls = []

    class Executor:
        def run(self, task, wd, feedback=None):
            calls.append(wd)
            event = threading.Event()
            # Cancel only after the grandchild has made the partial edit this
            # test promises to retain. A fixed timer races process startup on
            # loaded CI runners and can cancel before any edit exists.
            def cancel_after_partial_edit():
                target = Path(wd) / "implementation.py"
                deadline = time.monotonic() + 2.5
                while time.monotonic() < deadline:
                    if target.is_file() and target.read_text() == BODY:
                        break
                    time.sleep(.01)
                event.set()
            watcher = threading.Thread(target=cancel_after_partial_edit, daemon=True) if mode == "cancelled" else None
            child = f"from pathlib import Path; import time; p=Path('implementation.py'); " \
                    f"\nwhile True: p.write_text({BODY!r}); time.sleep(.02)"
            code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); " \
                   "print('partial stdout',flush=True); print('partial stderr',file=sys.stderr,flush=True); time.sleep(60)"
            if watcher:
                watcher.start()
            try:
                process = run_process([sys.executable, "-c", code], wd, timeout=3, cancel=event)
            finally:
                if watcher:
                    watcher.join(timeout=.5)
            return ExecutorResult(False, "", raw_log=process.output, process=process.metadata())

    if mode == "cancelled":
        with pytest.raises(KeyboardInterrupt):
            run(delivery_repo, executor=Executor())
    else:
        result = run(delivery_repo, executor=Executor())
        assert result.failed == ["A"] and not result.completed
    assert len(calls) == 1
    wd = Path(calls[0])
    assert wd.is_dir() and (wd / "implementation.py").read_text() == BODY
    before = (wd / "implementation.py").stat().st_mtime_ns
    time.sleep(.1)
    assert (wd / "implementation.py").stat().st_mtime_ns == before
    evidence = list((delivery_repo / ".cld").rglob("dispatch.json"))
    assert len(evidence) == 1
    process = json.loads(evidence[0].read_text())["process"]
    assert process["error"] == mode
    assert "partial stdout" in Path(process["stdout_path"]).read_text()
    assert "partial stderr" in Path(process["stderr_path"]).read_text()
    assert Path(process["stdout_path"]).is_relative_to(delivery_repo / ".cld")
    outcome = json.loads(evidence[0].parent.parent.joinpath("outcome.json").read_text())
    assert checked_git(["show", f'{outcome["recovery_ref"]}:implementation.py'], delivery_repo) == BODY


def test_cancelled_later_worker_stops_earlier_running_process(delivery_repo):
    barrier = threading.Barrier(2, timeout=10)
    stopped = []

    class Executor:
        def run(self, task, wd, feedback=None):
            barrier.wait()
            if task.id == "B":
                raise KeyboardInterrupt("cancel from later worker")
            result = run_process([sys.executable, "-c", "import time; time.sleep(60)"], wd, timeout=30)
            stopped.append(result)
            return ExecutorResult(False, "", process=result.metadata())

    started = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        run(delivery_repo, executor=Executor(), slices=[task("A"), task("B")], max_workers=2)
    assert time.monotonic() - started < 15
    assert len(stopped) == 1 and stopped[0].error == "cancelled"


def test_unconfirmed_cleanup_retains_worktree_without_candidate_inspection(delivery_repo):
    from cld.process import ProcessCleanupError
    calls = []

    class Executor:
        def run(self, task, wd, feedback=None):
            calls.append(wd)
            raise ProcessCleanupError("fixture: no termination confirmation")

    with pytest.raises(ProcessCleanupError):
        run(delivery_repo, executor=Executor())
    assert len(calls) == 1 and Path(calls[0]).is_dir()
    outcomes = list((delivery_repo / ".cld").rglob("outcome.json"))
    record = json.loads(outcomes[0].read_text())
    assert record["state"] == "cleanup_unconfirmed"
    assert "recovery_ref" not in record  # No post-dispatch capture of a possibly live tree.
