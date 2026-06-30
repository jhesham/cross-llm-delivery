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
    # argv[0] is the resolved opencode command: bare name, .cmd shim, or (on Windows
    # with the real exe found) the full path to opencode.exe.
    assert "opencode" in argv[0].lower()
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


def test_default_runner_detaches_stdin(monkeypatch):
    # ROOT CAUSE of a live hang (found dogfooding): a real gemini-3.1-pro dispatch
    # produced ZERO output and hung for 160s. opencode.exe, invoked directly (the
    # long-prompt path that bypasses the .cmd shim), BLOCKS forever reading an
    # inherited stdin. The identical dispatch with stdin closed completed, wrote the
    # file, and ran pytest to green. The runner MUST detach stdin (DEVNULL) so a
    # dispatched CLI can never block on the parent's stdin.
    import cld_providers.opencode.provider as mod

    captured = {}

    class _P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run",
                        lambda args, **kw: captured.update(kw) or _P())
    mod._default_runner(["opencode", "run", "x"], ".")
    assert captured.get("stdin") is mod.subprocess.DEVNULL


def test_parse_opencode_usage_captures_cost():
    # opencode reports a per-step dollar cost on step_finish; it must be accumulated
    # alongside tokens so dispatch_end / the by-model rollup can show real $.
    from cld_providers.opencode.provider import parse_opencode_usage
    raw = ('{"type":"step_finish","part":{"tokens":{"input":10,"total":15},"cost":0.01}}\n'
           '{"type":"step_finish","part":{"tokens":{"total":5},"cost":0.02}}')
    u = parse_opencode_usage(raw)
    assert u["total"] == 20
    assert abs(u["cost"] - 0.03) < 1e-9


def test_oc_cmd_prefers_real_exe_on_windows(monkeypatch):
    # BUG (found live): the opencode.cmd npm shim routes through cmd.exe /c, which
    # MANGLES a long multi-line prompt passed as a positional arg -> the dispatch
    # silently falls back to interactive/attach mode and produces no step_finish.
    # The real opencode.exe (invoked directly by subprocess, no shell) handles the
    # argv correctly. _oc_cmd must resolve the real .exe on Windows when findable.
    # Patch the impl module (cld_providers.opencode.provider) — that is where the
    # code actually lives; patching a re-export shim would have no effect.
    import cld_providers.opencode.provider as mod

    monkeypatch.delenv("OPENCODE_CLI_CMD", raising=False)
    monkeypatch.setattr(mod.os, "name", "nt", raising=False)
    # simulate the npm layout: shim on PATH, real exe under node_modules/.../bin
    monkeypatch.setattr(mod.shutil, "which",
                        lambda n: r"C:\npm\opencode.cmd" if n == "opencode.cmd" else None)
    monkeypatch.setattr(mod.os.path, "exists",
                        lambda p: p.replace("\\", "/").endswith(
                            "node_modules/opencode-ai/bin/opencode.exe"))

    cmd = mod._oc_cmd()
    assert cmd.replace("\\", "/").endswith("opencode-ai/bin/opencode.exe"), cmd


def test_oc_cmd_falls_back_to_cmd_when_exe_missing(monkeypatch):
    # if the real exe can't be located, fall back to the .cmd shim (still works for
    # short prompts; better than crashing). Override still wins.
    # Patch the impl module (cld_providers.opencode.provider) — shim has no os/shutil.
    import cld_providers.opencode.provider as mod
    monkeypatch.delenv("OPENCODE_CLI_CMD", raising=False)
    monkeypatch.setattr(mod.os, "name", "nt", raising=False)
    monkeypatch.setattr(mod.shutil, "which", lambda n: None)
    monkeypatch.setattr(mod.os.path, "exists", lambda p: False)
    assert mod._oc_cmd() == "opencode.cmd"


def test_oc_cmd_env_override_wins(monkeypatch):
    # Patch the impl module (cld_providers.opencode.provider) — shim has no os.
    import cld_providers.opencode.provider as mod
    monkeypatch.setenv("OPENCODE_CLI_CMD", "/custom/opencode")
    assert mod._oc_cmd() == "/custom/opencode"


def test_opencode_effort_maps_to_variant():
    runner = _ok_runner()
    ex = OpenCodeExecutor(runner=runner, model="opencode/gpt-5", effort="high")
    ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
    argv = runner.calls[0][0]
    assert "--variant" in argv and "high" in argv
