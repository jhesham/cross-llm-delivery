import os
from pathlib import Path
from cld_providers.antigravity.provider import (
    _dispatch_cwd, _parse_conversation_id, _transcript_path, _extract_model_reply,
)


def test_dispatch_cwd_is_on_system_drive():
    cwd = _dispatch_cwd()
    sysdrive = os.environ.get("SystemDrive", "C:")
    # the dispatch cwd must live on the system drive so agy's POSIX /Users/... path resolves
    assert cwd.upper().startswith(sysdrive.upper())


def test_parse_conversation_id_picks_most_frequent_uuid():
    log = (
        "I0622 server.go:840] Stream goroutine exited for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 conversation_manager.go:601] Stream completed for 4479fde7-507f-4dd9-83c3-f23ce0fe36bd\n"
        "I0622 something about aaaaaaaa-1111-2222-3333-444444444444 once\n"
    )
    assert _parse_conversation_id(log) == "4479fde7-507f-4dd9-83c3-f23ce0fe36bd"


def test_parse_conversation_id_none_when_absent():
    assert _parse_conversation_id("no uuids here") is None


def test_transcript_path_layout():
    p = _transcript_path("C:\\Users\\Administrator", "abc")
    assert p.endswith(os.path.join(
        ".gemini", "antigravity-cli", "brain", "abc", ".system_generated", "logs", "transcript.jsonl"))


def test_extract_model_reply_joins_model_steps():
    transcript = (
        '{"step_index":0,"source":"USER_EXPLICIT","content":"hi"}\n'
        '{"step_index":3,"source":"MODEL","type":"PLANNER_RESPONSE","content":"READY"}\n'
        '{"step_index":4,"source":"SYSTEM","content":"ignore me"}\n'
    )
    assert _extract_model_reply(transcript) == "READY"


def test_extract_model_reply_none_when_no_model_step():
    assert _extract_model_reply('{"source":"USER_EXPLICIT","content":"hi"}\n') is None
    assert _extract_model_reply("not json\n\n") is None


# ---------------------------------------------------------------------------
# Task 2: AntigravityExecutor tests
# ---------------------------------------------------------------------------

from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld_providers.antigravity.provider import AntigravityExecutor


class _Runner:
    """Injected runner. Writes the agy --log-file as a side effect (simulating agy),
    and answers git capture_diff calls."""
    def __init__(self, conv_id, *, dispatch_rc=0, diff="--- a\n+++ b\n+x\n", names="src/x.py\n"):
        self.conv_id = conv_id; self.dispatch_rc = dispatch_rc
        self.diff = diff; self.names = names; self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        if "-p" in args and "--add-dir" in args:           # the agy dispatch
            # simulate agy writing its --log-file with the conversation id in it
            i = args.index("--log-file"); log = args[i + 1]
            Path(log).write_text(f"Stream completed for {self.conv_id}\n", encoding="utf-8")
            return (self.dispatch_rc, "")                    # stdout empty by design
        if "--name-only" in joined:
            return (0, self.names)
        if "diff" in joined:
            return (0, self.diff)
        return (0, "")


def _seed_transcript(home: Path, conv_id: str, content="READY"):
    d = home / ".gemini" / "antigravity-cli" / "brain" / conv_id / ".system_generated" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "transcript.jsonl").write_text(
        '{"source":"MODEL","type":"PLANNER_RESPONSE","content":"%s"}\n' % content, encoding="utf-8")


def _task():
    return SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")


def test_satisfies_protocol(tmp_path):
    assert isinstance(AntigravityExecutor(runner=_Runner("c"), home=str(tmp_path)), Executor)


def test_dispatch_argv_shape(tmp_path):
    conv = "11111111-1111-1111-1111-111111111111"
    _seed_transcript(tmp_path, conv)
    r = _Runner(conv)
    ex = AntigravityExecutor(runner=r, model="Gemini 3.1 Pro (High)", home=str(tmp_path))
    ex.run(_task(), str(tmp_path / "wt"))
    argv, cwd = r.calls[0]
    assert "-p" in argv
    assert "--model" in argv and "Gemini 3.1 Pro (High)" in argv
    assert "--add-dir" in argv and str(tmp_path / "wt") in argv
    assert "--dangerously-skip-permissions" in argv
    assert "--log-file" in argv
    assert cwd == str(tmp_path)                              # dispatch cwd = home (on C:), NOT the worktree


def test_success_reads_reply_and_diff(tmp_path):
    conv = "22222222-2222-2222-2222-222222222222"
    _seed_transcript(tmp_path, conv, content="DONE")
    ex = AntigravityExecutor(runner=_Runner(conv, diff="DIFF"), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is True and res.diff == "DIFF" and res.files_changed == ["src/x.py"]
    assert "DONE" in res.raw_log


def test_nonzero_dispatch_not_ok(tmp_path):
    ex = AntigravityExecutor(runner=_Runner("c", dispatch_rc=1), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is False


def test_missing_transcript_not_ok_with_hint(tmp_path):
    # runner reports success + a conv id, but no transcript on disk -> ok False + cwd hint
    ex = AntigravityExecutor(runner=_Runner("33333333-3333-3333-3333-333333333333"), home=str(tmp_path))
    res = ex.run(_task(), str(tmp_path / "wt"))
    assert res.ok is False and "C:" in res.raw_log
