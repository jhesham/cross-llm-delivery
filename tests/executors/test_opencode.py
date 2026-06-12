"""Tests for OpenCodeExecutor — the OpenCode CLI adapter (fake runner; no live calls).

Mirrors test_gemini.py: assert the locked argv (run, -m provider/model, --format json,
--dir), diff capture via the shared helper, and ok=False on a nonzero dispatch.
"""

from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld.executors.opencode import OpenCodeExecutor


class RecordingRunner:
    """Matches a substring of the joined command, returns canned (rc, out); records argv."""

    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        for match, rc, out in self._responses:
            if match in joined:
                return (rc, out)
        return (0, "")


def _ok_runner(diff="--- a\n+++ b\n+x\n"):
    return RecordingRunner([
        ("opencode", 0, '{"type":"step_finish","part":{"tokens":{"input":10,"output":5,"total":15}}}'),
        ("--name-only", 0, "src/x.py\n"),
        ("diff", 0, diff),
    ])


class FakeServer:
    """Stand-in for a per-dispatch `opencode serve` bound to the target repo.

    Records the cwd it was started in (must be the target repo, so the server
    binds to THAT project) and whether it was stopped (teardown must always run)."""

    def __init__(self):
        self.started_cwd = None
        self.stopped = False
        self.url = "http://127.0.0.1:65111"

    def start(self, cwd):
        self.started_cwd = cwd
        return self.url

    def stop(self):
        self.stopped = True


def _fake_server_factory(holder):
    def factory():
        s = FakeServer()
        holder.append(s)
        return s
    return factory


def _executor(**kw):
    """OpenCodeExecutor with a fake server (no real `opencode serve` spawned)."""
    kw.setdefault("server_factory", _fake_server_factory([]))
    return OpenCodeExecutor(**kw)


def test_satisfies_protocol():
    assert isinstance(_executor(runner=_ok_runner()), Executor)


def test_builds_locked_argv_in_attach_mode():
    # opencode `run --dir` is only AUTHORITATIVE when attaching to a server
    # ("path on remote server if attaching"). A plain `run` resolves the project
    # from cwd/git-root and drifts to the wrong repo (confirmed live: kimi kept
    # doing our smoketest sandbox). So the executor starts a per-dispatch server
    # bound to the target repo, then attaches the run to it with an authoritative
    # --dir.
    servers = []
    runner = _ok_runner()
    ex = OpenCodeExecutor(runner=runner, model="anthropic/claude-sonnet-4-6",
                          server_factory=_fake_server_factory(servers))
    task = SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")
    ex.run(task, "/work")

    # the server was started IN the target repo (binds it as that project)
    assert servers and servers[0].started_cwd == "/work"
    # and torn down afterwards
    assert servers[0].stopped is True

    argv = runner.calls[0][0]
    assert argv[0] in ("opencode", "opencode.cmd")
    assert "run" in argv
    assert "-m" in argv and "anthropic/claude-sonnet-4-6" in argv
    assert "--format" in argv and "json" in argv
    assert "--dir" in argv and "/work" in argv
    assert "do the thing" in " ".join(argv)
    assert "--dangerously-skip-permissions" in argv
    # attach to the per-dispatch server so --dir is authoritative
    assert "--attach" in argv and servers[0].url in argv
    # no bare --port in attach mode (the server owns the port)
    assert "--port" not in argv


def test_server_stopped_even_when_run_fails():
    # teardown must run in a finally — a failed dispatch can't leak a server
    servers = []
    runner = RecordingRunner([("opencode", 1, "boom")])
    ex = OpenCodeExecutor(runner=runner, server_factory=_fake_server_factory(servers))
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert res.ok is False
    assert servers[0].stopped is True


def test_captures_diff_and_files():
    ex = _executor(runner=_ok_runner(diff="DIFF"))
    task = SliceTask(id="T", brief="b", files=["src/x.py"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert isinstance(res, ExecutorResult)
    assert res.ok is True
    assert res.diff == "DIFF"
    assert res.files_changed == ["src/x.py"]


def test_nonzero_dispatch_not_ok():
    runner = RecordingRunner([("opencode", 1, "boom: model unavailable")])
    ex = _executor(runner=runner)
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert res.ok is False
    assert "boom" in res.raw_log


def test_non_jsonl_output_fails_dispatch_guard():
    # A permission-blocked or malformed run emits no JSONL step_finish event. Any
    # output without one must be treated as a FAILED dispatch, never trusted.
    runner = RecordingRunner([
        ("opencode", 0, "I implemented slice T1!\nAll 8 tests pass."),
    ])
    ex = _executor(runner=runner)
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert res.ok is False
    assert "step_finish" in res.raw_log  # guard explains itself
    # and the original output is preserved for diagnosis
    assert "I implemented slice T1!" in res.raw_log


def test_server_start_failure_does_not_leak():
    # If serve never reports a URL, start() must stop the proc before raising —
    # a leaked `opencode serve` kept dispatching for 25+ min (confirmed live).
    from cld.executors.opencode import _OpenCodeServer

    class _NoUrlProc:
        pid = 4242
        def __init__(self): self.stdout = self
        def readline(self): return ""        # never emits a URL
        def poll(self): return 0             # and exits immediately

    srv = _OpenCodeServer()
    stopped = {"n": 0}
    srv._make_proc = lambda cwd: _NoUrlProc()  # not used; we patch Popen below
    import cld.executors.opencode as mod
    orig_popen = mod.subprocess.Popen
    orig_run = mod.subprocess.run
    mod.subprocess.Popen = lambda *a, **k: _NoUrlProc()
    mod.subprocess.run = lambda *a, **k: stopped.__setitem__("n", stopped["n"] + 1)
    try:
        import pytest
        with pytest.raises(RuntimeError):
            srv.start("/work")
        # stop() ran (taskkill invoked) -> no orphan
        assert stopped["n"] >= 1 or srv._proc is None
        assert srv._proc is None
    finally:
        mod.subprocess.Popen = orig_popen
        mod.subprocess.run = orig_run


def test_default_runner_survives_non_utf8_console_bytes():
    # Live kimi-k2.6 validation crashed the reader thread: opencode emitted byte
    # 0x90 (invalid cp1252), and text=True without encoding= decodes with the
    # Windows locale codec. The runner must decode utf-8 with replacement.
    import sys
    from cld.executors.opencode import _default_runner
    rc, out = _default_runner(
        [sys.executable, "-c", r"import sys; sys.stdout.buffer.write(b'ok\x90end')"],
        ".")
    assert rc == 0
    assert "ok" in out and "end" in out  # decoded with replacement, not crashed
