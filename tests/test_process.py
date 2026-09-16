"""Offline process lifecycle contracts, executed on the host OS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from cld.process import run_process


def run(tmp_path, code, **kwargs):
    return run_process([sys.executable, "-c", code], str(tmp_path), artifact_dir=tmp_path / "logs", **kwargs)


def test_streams_encoding_stdin_and_environment(tmp_path):
    prompt = "α\nlong prompt " * 20000
    result = run(tmp_path,
        "import sys,os; data=sys.stdin.buffer.read().decode('utf-8'); print(len(data)); "
        "print(os.environ['CLD_FIXTURE']); sys.stdout.buffer.write(b'bad\\x90byte'); "
        "sys.stderr.buffer.write(b'other\\x90stream')", stdin=prompt,
        env={"CLD_FIXTURE": "fixture"}, timeout=10)
    assert result.returncode == 0 and result.error is None
    assert str(len(prompt)) in result.stdout and "fixture" in result.stdout
    assert "bad�byte" in result.stdout and "other�stream" in result.stderr
    assert b"\x90" in Path(result.stdout_path).read_bytes()
    metadata = Path(result.stdout_path).with_name("result.json").read_text()
    assert "long prompt" not in metadata and "CLD_FIXTURE" not in metadata


def test_default_stdin_is_eof(tmp_path):
    result = run(tmp_path, "import sys; print(repr(sys.stdin.read()))", timeout=5)
    assert result.error is None and "''" in result.stdout


def test_nonzero_preserves_writes_and_both_streams(tmp_path):
    result = run(tmp_path, "from pathlib import Path; import sys; Path('partial').write_text('saved'); "
                 "print('stdout'); print('stderr',file=sys.stderr); sys.exit(9)")
    assert result.returncode == 9 and result.error == "nonzero_exit"
    assert result.stdout.strip() == "stdout" and result.stderr.strip() == "stderr"
    assert (tmp_path / "partial").read_text() == "saved"


@pytest.mark.parametrize("text,error", [("authentication failed", "authentication"), ("ordinary failure", "nonzero_exit")])
def test_observable_authentication(tmp_path, text, error):
    result = run(tmp_path, f"import sys; print({text!r},file=sys.stderr); sys.exit(1)")
    assert result.error == error


def test_missing_and_access_denied(tmp_path):
    result = run_process([str(tmp_path / "missing")], tmp_path)
    assert result.error == "missing_binary" and result.returncode is None
    # Windows denies execution of a directory; POSIX denies a non-executable file.
    denied = tmp_path if os.name == "nt" else tmp_path / "denied"
    if os.name != "nt":
        denied.write_text("echo no")
    result = run_process([str(denied)], tmp_path)
    assert result.error == "access_denied"


@pytest.mark.parametrize("mode", ["timeout", "cancelled", "normal_exit"])
def test_descendants_stopped_before_return_and_partial_logs_retained(tmp_path, mode):
    child = "import time; from pathlib import Path; p=Path('heartbeat'); " \
            "\nwhile True: p.write_text(str(time.time())); time.sleep(.02)"
    code = ("import subprocess,sys,time; from pathlib import Path; "
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
            "Path('child.pid').write_text(str(p.pid)); print('partial stdout',flush=True); "
            "print('partial stderr',file=sys.stderr,flush=True); "
            "time.sleep(.4)" + ("; time.sleep(60)" if mode != "normal_exit" else ""))
    cancel = threading.Event()
    timer = threading.Timer(1.2, cancel.set) if mode == "cancelled" else None
    if timer:
        timer.start()
    try:
        result = run(tmp_path, code, timeout=1.5 if mode == "timeout" else 10, cancel=cancel)
    finally:
        if timer:
            timer.cancel()
    assert result.error == (None if mode == "normal_exit" else mode)
    assert result.elapsed < 8
    assert "partial stdout" in result.stdout and "partial stderr" in result.stderr
    assert (tmp_path / "child.pid").exists()
    before = (tmp_path / "heartbeat").read_bytes()
    time.sleep(.15)
    assert (tmp_path / "heartbeat").read_bytes() == before


def test_precancel_does_not_launch(tmp_path):
    event = threading.Event(); event.set()
    result = run(tmp_path, "from pathlib import Path; Path('should-not-exist').touch()", cancel=event)
    assert result.error == "cancelled" and not (tmp_path / "should-not-exist").exists()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_invalid_deadlines_rejected_before_launch(tmp_path, value):
    with pytest.raises(ValueError):
        run(tmp_path, "raise Exception('not launched')", timeout=value)


def test_keyboard_interrupt_cleans_tree_and_attaches_evidence(tmp_path, monkeypatch):
    original = subprocess.Popen.communicate
    raised = False

    def interrupt_once(self, *args, **kwargs):
        nonlocal raised
        if not raised:
            raised = True
            # Let the bootstrap start the target, then emulate main-thread Ctrl-C.
            try:
                original(self, *args, **{**kwargs, "timeout": .4})
            except subprocess.TimeoutExpired:
                pass
            raise KeyboardInterrupt()
        return original(self, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupt_once)
    with pytest.raises(KeyboardInterrupt) as exc:
        run(tmp_path, "import time; print('before interrupt',flush=True); time.sleep(60)")
    result = exc.value.process_result
    assert result.error == "cancelled" and "before interrupt" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows Job assignment failure")
def test_job_assignment_failure_never_launches_target(tmp_path, monkeypatch):
    from cld._windows_job import Job

    def denied(*args):
        raise PermissionError("fixture")

    monkeypatch.setattr(Job, "assign", denied)
    result = run(tmp_path, "from pathlib import Path; Path('escaped').touch()")
    assert result.error == "access_denied" and not (tmp_path / "escaped").exists()
