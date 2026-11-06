"""v0.6.0 AGYSERIAL: Antigravity dispatches never overlap, on this machine, however they were selected."""
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from cld.executors.base import ExecutorResult, SliceTask
from cld.ledger import Ledger
from cld.orchestrator import run_plan_parallel

from tests.evidence._lazy import resolve

ROOT = Path(__file__).resolve().parents[2]
AGY = "antigravity:Gemini 4 Argon (High)"
CODEX = "codex:gpt-6.1-sol@high"
CODEX_MARK = "codex-was-here"
TEMP_VARS = ("TEMP", "TMP", "TMPDIR")


@pytest.fixture(autouse=True)
def _private_lock_dir(tmp_path, monkeypatch):
    lock_dir = tmp_path / "locks"
    monkeypatch.setenv("CLD_DISPATCH_LOCK_DIR", str(lock_dir))
    return lock_dir


class _Tracker:
    """Shared across builds: records per-provider overlap and dispatch start times."""

    def __init__(self, *, raise_on=None, raise_with=RuntimeError):
        self.lock = threading.Lock()
        self.active, self.peak, self.started = {}, {}, {}
        self.peak_total = 0
        self.raise_on, self.raise_with = raise_on, raise_with

    def executor(self, spec, **_kwargs):
        tracker, provider = self, spec.split(":", 1)[0]

        class _Ex:
            def run(self, task, workdir, feedback=None):
                with tracker.lock:
                    tracker.active[provider] = tracker.active.get(provider, 0) + 1
                    tracker.peak[provider] = max(tracker.peak.get(provider, 0), tracker.active[provider])
                    tracker.peak_total = max(tracker.peak_total, sum(tracker.active.values()))
                    tracker.started.setdefault((task.id, provider), time.time())
                try:
                    time.sleep(0.4 if provider == "codex" else 0.15)
                    if tracker.raise_on == (task.id, provider):
                        raise tracker.raise_with("executor crashed")
                finally:
                    with tracker.lock:
                        tracker.active[provider] -= 1
                files = [f"src/{task.id}.py"] + ([CODEX_MARK] if provider == "codex" else [])
                return ExecutorResult(ok=True, diff="", files_changed=files, raw_log="1 passed in 0.1s")
        return _Ex()


def _slice(sid, executor=None):
    return SliceTask(id=sid, brief="b", files=[f"src/{sid}.py"], acceptance_test_path="t.py",
                     executor=executor)


def _judge(files_changed=(), **_kwargs):
    # The codex rung "fails" so fallback planners move on to the next rung.
    passed = CODEX_MARK not in files_changed
    return type("J", (), {"passed": passed, "failing_tests": [] if passed else ["codex rung failed"]})()


def _run(tmp_path, slices, tracker, *, default_spec, workers, rung_planner=None, name="l"):
    return run_plan_parallel(slices, Ledger(str(tmp_path / f"{name}.json")),
                             executor_factory=tracker.executor, default_spec=default_spec,
                             judge_fn=_judge, test_runner=lambda *a, **k: "1 passed",
                             max_workers=workers, rung_planner=rung_planner, simulation=True)


def _user_dirs(tmp_path):
    """Per-user folders under tmp_path: (environment, the lock folder CLD must then use)."""
    user = tmp_path / "user"
    if os.name == "nt":
        local = user / "AppData" / "Local"
        return {"LOCALAPPDATA": str(local)}, local / "cld" / "locks"
    return {"HOME": str(user)}, user / ".cache" / "cld" / "locks"


def _point_temp_at(monkeypatch, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for var in TEMP_VARS:
        monkeypatch.setenv(var, str(folder))
    monkeypatch.setattr(tempfile, "tempdir", None)


def _hold_slot_in_child(spec, seconds, stamp_dir, env=None):
    """Start a separate process that holds the dispatch slot; return (process, release_time_file).

    The child inherits this process's environment (including CLD_DISPATCH_LOCK_DIR when set),
    with env applied on top."""
    stamp = stamp_dir / f"released-{time.time_ns()}.txt"
    code = (
        "import sys, time\n"
        "from cld.dispatch_limits import dispatch_slot\n"
        f"with dispatch_slot({spec!r}):\n"
        "    print('held', flush=True)\n"
        f"    time.sleep({seconds})\n"
        f"    open({str(stamp)!r}, 'w').write(repr(time.time()))\n"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT / "engine"), str(ROOT))),
           "PYTHONDONTWRITEBYTECODE": "1", **(env or {})}
    child = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    line = child.stdout.readline().strip()
    assert line == "held", (line, child.stderr.read() if child.poll() is not None else "")
    return child, stamp


def test_antigravity_declares_one_dispatch_at_a_time():
    load = resolve("cld.providers_api", "load_providers")
    get = resolve("cld.providers_api", "get_provider")
    load()
    assert getattr(get("antigravity"), "max_parallel_dispatches", None) == 1
    for name in ("codex", "claude", "opencode", "cursor"):
        assert getattr(get(name), "max_parallel_dispatches", "missing") is None, name


def test_lock_lives_in_the_override_dir(_private_lock_dir):
    lock_path = resolve("cld.dispatch_limits", "lock_path")
    assert Path(lock_path("antigravity")).parent == _private_lock_dir


def test_default_lock_dir_is_per_user_and_ignores_temp(tmp_path, monkeypatch):
    # TEMP can differ per login session (Temp\2 on a terminal server) or per process.
    lock_path = resolve("cld.dispatch_limits", "lock_path")
    monkeypatch.delenv("CLD_DISPATCH_LOCK_DIR")
    env, expected = _user_dirs(tmp_path)
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    paths = []
    for name in ("temp-a", "temp-b"):
        _point_temp_at(monkeypatch, tmp_path / name)
        paths.append(Path(lock_path("antigravity")))
    assert paths[0] == paths[1], f"the lock moved with TEMP: {paths}"
    assert paths[0].parent == expected, paths[0]
    assert "antigravity" in paths[0].name


def test_per_slice_antigravity_pins_never_overlap_under_a_codex_default(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    tracker = _Tracker()
    result = _run(tmp_path, [_slice("A", AGY), _slice("B", AGY), _slice("C", AGY), _slice("D")],
                  tracker, default_spec=CODEX, workers=4)
    assert sorted(result.completed) == ["A", "B", "C"]
    assert tracker.peak.get("antigravity") == 1, tracker.peak
    assert tracker.peak_total >= 2, "the codex slice must still run alongside antigravity"


def test_planner_entry_rungs_on_antigravity_never_overlap(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    tracker = _Tracker()
    planner = lambda task: [("workhorse", AGY, 1)]
    result = _run(tmp_path, [_slice("A"), _slice("B"), _slice("C")], tracker,
                  default_spec=CODEX, workers=3, rung_planner=planner)
    assert sorted(result.completed) == ["A", "B", "C"]
    assert tracker.peak.get("antigravity") == 1, tracker.peak


def test_codex_to_antigravity_fallback_never_overlaps_on_antigravity(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    tracker = _Tracker()
    planner = lambda task: [("workhorse", CODEX, 1), ("heavy", AGY, 1)]
    result = _run(tmp_path, [_slice("A"), _slice("B"), _slice("C")], tracker,
                  default_spec=CODEX, workers=3, rung_planner=planner)
    assert sorted(result.completed) == ["A", "B", "C"]
    assert tracker.peak.get("codex", 0) >= 2, "codex rungs keep running in parallel"
    assert tracker.peak.get("antigravity") == 1, tracker.peak


def test_the_slot_is_released_after_an_executor_exception(tmp_path):
    dispatch_slot = resolve("cld.dispatch_limits", "dispatch_slot")
    tracker = _Tracker(raise_on=("A", "antigravity"))
    try:
        _run(tmp_path, [_slice("A", AGY)], tracker, default_spec=CODEX, workers=1)
    except Exception:
        pass
    acquired = threading.Event()

    def take():
        with dispatch_slot(AGY):
            acquired.set()
    worker = threading.Thread(target=take, daemon=True)
    worker.start()
    assert acquired.wait(5), "the Antigravity slot was not released after the executor raised"


def test_two_builds_at_once_never_overlap_on_antigravity(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    tracker = _Tracker()
    errors = []

    def build(name):
        try:
            _run(tmp_path, [_slice(f"{name}1", AGY), _slice(f"{name}2", AGY)], tracker,
                 default_spec=CODEX, workers=2, name=name)
        except BaseException as exc:  # surface in the main thread
            errors.append(exc)
    threads = [threading.Thread(target=build, args=(n,)) for n in ("X", "Y")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    assert tracker.peak.get("antigravity") == 1, tracker.peak


def test_another_process_holding_the_slot_delays_dispatch(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    child, stamp = _hold_slot_in_child(AGY, 1.0, tmp_path)
    try:
        tracker = _Tracker()
        result = _run(tmp_path, [_slice("A", AGY)], tracker, default_spec=CODEX, workers=1)
    finally:
        child.wait(30)
    assert result.completed == ["A"]
    released = float(stamp.read_text())
    assert tracker.started[("A", "antigravity")] >= released - 0.05, (tracker.started, released)


def test_processes_with_different_temp_dirs_share_one_slot(tmp_path, monkeypatch):
    resolve("cld.dispatch_limits", "dispatch_slot")
    monkeypatch.delenv("CLD_DISPATCH_LOCK_DIR")
    env, _ = _user_dirs(tmp_path)
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    child_temp = tmp_path / "child-temp"
    child_temp.mkdir()
    child, stamp = _hold_slot_in_child(AGY, 1.0, tmp_path,
                                       env={var: str(child_temp) for var in TEMP_VARS})
    try:
        _point_temp_at(monkeypatch, tmp_path / "parent-temp")
        tracker = _Tracker()
        result = _run(tmp_path, [_slice("A", AGY)], tracker, default_spec=CODEX, workers=1)
    finally:
        child.wait(30)
    assert result.completed == ["A"]
    released = float(stamp.read_text())
    assert tracker.started[("A", "antigravity")] >= released - 0.05, (tracker.started, released)


def test_another_process_holding_the_slot_does_not_delay_codex(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    child, stamp = _hold_slot_in_child(AGY, 2.0, tmp_path)
    try:
        tracker = _Tracker()
        _run(tmp_path, [_slice("A", CODEX)], tracker, default_spec=CODEX, workers=1)
        codex_started = tracker.started[("A", "codex")]
    finally:
        child.wait(30)
    assert codex_started < float(stamp.read_text()), "codex must not wait for the Antigravity slot"


def test_model_validation_waits_for_the_slot(tmp_path):
    resolve("cld.dispatch_limits", "dispatch_slot")
    validate_model = resolve("cld.validate", "validate_model")
    started = []

    class _Ex:
        def run(self, task, workdir, feedback=None):
            started.append(time.time())
            return ExecutorResult(ok=False, diff="", files_changed=[], raw_log="no")

    def git(args, cwd):
        done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        return done.returncode, done.stdout + done.stderr

    child, stamp = _hold_slot_in_child(AGY, 1.0, tmp_path)
    try:
        validate_model(AGY, executor=_Ex(), git_runner=git, base_dir=str(tmp_path / "probe"))
    except Exception:
        pass
    finally:
        child.wait(30)
    assert started, "validation never dispatched"
    assert started[0] >= float(stamp.read_text()) - 0.05, "validation dispatched while another process held the slot"


def test_a_cancelled_wait_gives_up_without_taking_the_slot(tmp_path):
    dispatch_slot = resolve("cld.dispatch_limits", "dispatch_slot")
    child, _ = _hold_slot_in_child(AGY, 10.0, tmp_path)
    cancel = threading.Event()
    timer = threading.Timer(0.3, cancel.set)
    entered, began = [], time.monotonic()
    timer.start()
    try:
        with pytest.raises(KeyboardInterrupt):
            with dispatch_slot(AGY, cancel=cancel):
                entered.append(True)
        elapsed = time.monotonic() - began
    finally:
        timer.cancel()
        child.kill()
        child.wait(10)
    assert not entered, "entered the slot after the wait was cancelled"
    assert elapsed < 3, f"the cancelled wait took {elapsed:.1f}s"


def test_cancelling_the_build_stops_a_dispatch_waiting_for_the_slot(tmp_path):
    # B (codex) is interrupted while A waits for the slot another process holds; the
    # build's cancellation must end A's wait without dispatching it.
    resolve("cld.dispatch_limits", "dispatch_slot")
    child, _ = _hold_slot_in_child(AGY, 10.0, tmp_path)
    tracker = _Tracker(raise_on=("B", "codex"), raise_with=KeyboardInterrupt)
    began = time.monotonic()
    try:
        with pytest.raises(KeyboardInterrupt):
            _run(tmp_path, [_slice("A", AGY), _slice("B")], tracker, default_spec=CODEX, workers=2)
        elapsed = time.monotonic() - began
    finally:
        child.kill()
        child.wait(10)
    assert ("A", "antigravity") not in tracker.started, "A was dispatched after the build was cancelled"
    assert elapsed < 5, f"the cancelled build waited {elapsed:.1f}s for the Antigravity slot"
