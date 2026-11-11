"""v0.7.1 CANCELENGINE: an external cancel flag with Ctrl+C semantics.

Behaviour that depends on process-global state runs in a subprocess that prints one
JSON object; the test asserts on it.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from tests.evidence._lazy import resolve
from tests.v070 import _stubs

ROOT = Path(__file__).resolve().parents[2]
ENGINE = str(ROOT / "engine")
CHILD = ("import os, sys, time\nopen(sys.argv[1] + '.tmp', 'w').write(str(os.getpid()))\n"
         "os.replace(sys.argv[1] + '.tmp', sys.argv[1])\ntime.sleep(120)\n")


def _script(tmp_path, body, *args, env=None, timeout=60):
    script = tmp_path / "script.py"
    script.write_text(f"import json, os, sys, threading, time\nsys.path.insert(0, {ENGINE!r})\n"
                      f"CHILD = {CHILD!r}\n" + body, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True,
                          text=True, timeout=timeout, env={**os.environ, **(env or {})},
                          cwd=tmp_path)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    assert lines, f"script printed no result: rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    return json.loads(lines[-1])


def _pids(directory):
    return [int(p.read_text()) for p in Path(directory).iterdir() if p.suffix != ".tmp"]


_RUN_PROCESS = """
from cld import process
process.start_cancel_watcher()
cancel_file, pidfile = os.environ["CLD_CANCEL_FILE"], sys.argv[1]
fired = []
def fire():
    for _ in range(400):
        if os.path.exists(pidfile):
            break
        time.sleep(0.025)
    time.sleep(0.3)
    open(cancel_file, "w").write("cancel")
    fired.append(time.monotonic())
threading.Thread(target=fire, daemon=True).start()
out = {}
try:
    result = process.run_process([sys.executable, "-c", CHILD, pidfile], os.getcwd(), timeout=120)
    out["returned_error"] = result.error
except KeyboardInterrupt as exc:
    out["interrupted"] = True
    out["has_result"] = getattr(exc, "process_result", None) is not None
out["after_fire"] = (time.monotonic() - fired[0]) if fired else None
print(json.dumps(out))
"""


def test_external_cancel_interrupts_run_process(tmp_path):
    resolve("cld.process", "start_cancel_watcher")
    pidfile = tmp_path / "child.pid"
    out = _script(tmp_path, _RUN_PROCESS, pidfile,
                  env={"CLD_CANCEL_FILE": str(tmp_path / "cancel.request")})
    assert out.get("interrupted") is True, f"external cancel must raise KeyboardInterrupt: {out}"
    assert out["has_result"] is True
    assert out["after_fire"] is not None and out["after_fire"] < 3, out
    assert not _stubs.pid_alive(int(pidfile.read_text())), "child survived the cancel"


_PARALLEL = """
from cld import process
from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel
pids, cancel_file = sys.argv[1], os.environ["CLD_CANCEL_FILE"]
dispatched = []
class Exec:
    def run(self, task, workdir):
        dispatched.append(task.id)
        if MODE == "blocked":
            process.run_process([sys.executable, "-c", CHILD, os.path.join(pids, task.id)],
                                os.getcwd(), timeout=120)
        else:
            open(cancel_file, "w").write("cancel")
            for _ in range(200):
                if process.EXTERNAL_CANCEL.is_set():
                    break
                time.sleep(0.01)
        return ExecutorResult(ok=True, diff="", files_changed=[f"src/{task.id}.py"],
                              raw_log="1 passed in 0.1s")
def judge(files_changed, allowed, run_tests):
    from cld.judge import judge as j
    return j(files_changed=files_changed, allowed=allowed, run_tests=run_tests)
fired = []
def fire():
    for _ in range(400):
        if len(os.listdir(pids)) >= 2:
            break
        time.sleep(0.025)
    time.sleep(0.3)
    open(cancel_file, "w").write("cancel")
    fired.append(time.monotonic())
if MODE == "blocked":
    threading.Thread(target=fire, daemon=True).start()
slices = [SliceTask(id=i, brief="b", files=[f"src/{i}.py"], acceptance_test_path="t.py", deps=[])
          for i in ("A", "B")]
out = {}
try:
    run_plan_parallel(slices, Ledger(os.path.join(pids, "..", "ledger.json")), executor=Exec(),
                      judge_fn=judge, max_workers=WORKERS, simulation=True)
    out["completed"] = True
except KeyboardInterrupt:
    out["interrupted"] = True
out["after_fire"] = (time.monotonic() - fired[0]) if fired else None
out["dispatched"] = dispatched
print(json.dumps(out))
"""


def test_blocked_parallel_step_wakes_on_external_cancel(tmp_path):
    resolve("cld.process", "EXTERNAL_CANCEL")
    pids = tmp_path / "pids"
    pids.mkdir()
    out = _script(tmp_path, "MODE, WORKERS = 'blocked', 2\n" + _PARALLEL, pids,
                  env={"CLD_CANCEL_FILE": str(tmp_path / "cancel.request")})
    assert out.get("interrupted") is True, f"the step must end with KeyboardInterrupt: {out}"
    assert out["after_fire"] is not None and out["after_fire"] < 3, out
    children = _pids(pids)
    assert len(children) == 2, children
    assert not any(_stubs.pid_alive(pid) for pid in children), "a sleeping child survived"


def test_no_new_dispatch_after_the_flag_is_set(tmp_path):
    resolve("cld.process", "EXTERNAL_CANCEL")
    pids = tmp_path / "pids"
    pids.mkdir()
    out = _script(tmp_path, "MODE, WORKERS = 'first', 1\n" + _PARALLEL, pids,
                  env={"CLD_CANCEL_FILE": str(tmp_path / "cancel.request")})
    assert out.get("interrupted") is True, out
    assert len(out["dispatched"]) == 1, f"a slice was dispatched after the cancel: {out}"


def test_watcher_sets_linked_events(tmp_path, monkeypatch):
    process = resolve("cld.process")
    start, link = resolve("cld.process", "start_cancel_watcher"), resolve("cld.process", "link_external_cancel")
    cancel_file = tmp_path / "cancel.request"
    monkeypatch.setenv("CLD_CANCEL_FILE", str(cancel_file))
    event = threading.Event()
    link(event)
    start()
    start()  # idempotent
    cancel_file.write_text("cancel")
    assert event.wait(2), "a linked event did not observe the external cancel"
    assert process.EXTERNAL_CANCEL.is_set()


def test_no_watcher_without_the_variable():
    start = resolve("cld.process", "start_cancel_watcher")
    before = {t.ident for t in threading.enumerate()}
    start()
    assert {t.ident for t in threading.enumerate()} == before


_HOLDER = """
from cld.dispatch_limits import dispatch_slot
with dispatch_slot("antigravity:Gemini 4 Argon (High)"):
    open(sys.argv[1], "w").write("held")
    time.sleep(60)
"""


def test_slot_wait_gives_up_within_a_second(tmp_path, monkeypatch):
    flag = resolve("cld.process", "EXTERNAL_CANCEL")
    from cld.dispatch_limits import dispatch_slot
    monkeypatch.setenv("CLD_DISPATCH_LOCK_DIR", str(tmp_path / "locks"))
    script = tmp_path / "holder.py"
    script.write_text(f"import sys, time\nsys.path.insert(0, {ENGINE!r})\n" + _HOLDER, encoding="utf-8")
    held = tmp_path / "held"
    holder = subprocess.Popen([sys.executable, str(script), str(held)],
                              env={**os.environ, "CLD_DISPATCH_LOCK_DIR": str(tmp_path / "locks")})
    try:
        assert _stubs.wait_for(held.exists, 20), "holder never took the slot"
        threading.Timer(0.3, flag.set).start()
        t0 = time.monotonic()
        interrupted = False
        try:
            with dispatch_slot("antigravity:Gemini 4 Argon (High)"):
                pass
        except KeyboardInterrupt:
            interrupted = True
        assert interrupted, "the slot was acquired although another process holds it"
        assert time.monotonic() - t0 < 1.5
    finally:
        holder.kill()
        holder.wait(10)


def test_recovery_does_not_record_an_external_cancel_as_failure(tmp_path):
    flag = resolve("cld.process", "EXTERNAL_CANCEL")
    from cld.executors.base import SliceTask
    from cld.recovery import RecoverySession
    task = SliceTask(id="A", brief="b", files=["a.py"], acceptance_test_path="t.py")
    (tmp_path / "wt").mkdir()
    session = RecoverySession(str(tmp_path), str(tmp_path / "wt"), task, str(tmp_path / "l.json"),
                              None, base="0" * 40, artifact_root=str(tmp_path / "art"))
    flag.set()
    try:
        session.failure(KeyboardInterrupt("cancel"))
    finally:
        flag.clear()
    assert session.record["state"] != "failed", session.record


def test_recovery_still_records_ordinary_failures(tmp_path):
    from cld.executors.base import SliceTask
    from cld.recovery import RecoverySession
    task = SliceTask(id="A", brief="b", files=["a.py"], acceptance_test_path="t.py")
    (tmp_path / "wt").mkdir()
    session = RecoverySession(str(tmp_path), str(tmp_path / "wt"), task, str(tmp_path / "l.json"),
                              None, base="0" * 40, artifact_root=str(tmp_path / "art"))
    session.failure(RuntimeError("boom"))
    assert session.record["state"] == "failed"
