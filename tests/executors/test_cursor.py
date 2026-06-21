import os

from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld.executors.cursor import CursorExecutor


class RecordingRunner:
    def __init__(self, responses): self._r = responses; self.calls = []
    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        for match, rc, out in self._r:
            if match in joined:
                return (rc, out)
        return (0, "")


def _ok_runner(diff="--- a\n+++ b\n+x\n"):
    return RecordingRunner([
        ("cursor", 0, '{"type":"result","is_error":false,"usage":{"inputTokens":10,"outputTokens":5}}'),
        ("--name-only", 0, "src/x.py\n"),
        ("diff", 0, diff),
    ])


def test_satisfies_protocol():
    assert isinstance(CursorExecutor(runner=_ok_runner()), Executor)


def test_builds_locked_argv():
    runner = _ok_runner()
    ex = CursorExecutor(runner=runner, model="composer-2.5")
    ex.run(SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py"), "/work")
    argv = runner.calls[0][0]
    assert "cursor" in argv[0].lower()
    assert "-p" in argv
    assert "--output-format" in argv and "json" in argv
    assert "--workspace" in argv and "/work" in argv
    assert "--model" in argv and "composer-2.5" in argv
    assert "--force" in argv and "--trust" in argv
    assert "do the thing" in " ".join(argv)


def test_effort_maps_to_model_suffix():
    runner = _ok_runner()
    ex = CursorExecutor(runner=runner, model="claude-opus-4-8", effort="medium")
    ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
    argv = runner.calls[0][0]
    assert "claude-opus-4-8-medium" in argv


def test_nonzero_dispatch_not_ok():
    runner = RecordingRunner([("cursor", 1, "boom")])
    ex = CursorExecutor(runner=runner)
    res = ex.run(SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py"), "/work")
    assert res.ok is False and "boom" in res.raw_log


def test_captures_diff_on_success():
    ex = CursorExecutor(runner=_ok_runner(diff="DIFF"))
    res = ex.run(SliceTask(id="T", brief="b", files=["src/x.py"], acceptance_test_path="t.py"), "/work")
    assert res.ok is True and res.diff == "DIFF" and res.files_changed == ["src/x.py"]


def test_dispatch_has_no_cmd_shim(monkeypatch, tmp_path):
    # with a fake versions dir, the dispatched argv must use index.js, not cursor-agent.cmd
    monkeypatch.delenv("CURSOR_AGENT_CMD", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    v = tmp_path / "cursor-agent" / "versions" / "2026.06.15"
    v.mkdir(parents=True)
    (v / "index.js").write_text("//", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    runner = _ok_runner()
    CursorExecutor(runner=runner, model="composer-2.5").run(
        SliceTask(id="T", brief="b", files=["src/x.py"], acceptance_test_path="t.py"), "/work")
    argv = runner.calls[0][0]
    assert any(p.endswith("index.js") for p in argv)
    assert not any(p.endswith(".cmd") for p in argv)
