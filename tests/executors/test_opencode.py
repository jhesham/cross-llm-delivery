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


def _executor(**kw):
    return OpenCodeExecutor(**kw)


def test_satisfies_protocol():
    assert isinstance(_executor(runner=_ok_runner()), Executor)


def test_builds_locked_argv():
    # Plain headless run: -m model, --format json, --dir cwd, skip-permissions, --port.
    # A clean test proved this isolates the work dir correctly (no serve/attach needed).
    runner = _ok_runner()
    ex = OpenCodeExecutor(runner=runner, model="anthropic/claude-sonnet-4-6")
    task = SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")
    ex.run(task, "/work")

    argv = runner.calls[0][0]
    assert argv[0] in ("opencode", "opencode.cmd")
    assert "run" in argv
    assert "-m" in argv and "anthropic/claude-sonnet-4-6" in argv
    assert "--format" in argv and "json" in argv
    assert "--dir" in argv and "/work" in argv
    assert "do the thing" in " ".join(argv)
    assert "--dangerously-skip-permissions" in argv
    # bare --port last (fresh local server, isolates the session)
    assert argv[-1] == "--port"
    # no attach machinery anymore
    assert "--attach" not in argv


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
