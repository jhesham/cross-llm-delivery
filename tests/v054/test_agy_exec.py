"""v0.5.4 AGYEXEC: the Antigravity executor reads agy's JSON result, keeps work, records usage."""
import json
from pathlib import Path

from tests.evidence._lazy import resolve

PROVIDER_MODULE = "cld_providers.antigravity.provider"


def _executor(**kwargs):
    return resolve(PROVIDER_MODULE, "AntigravityExecutor")(**kwargs)


def _task():
    SliceTask = resolve("cld.executors.base", "SliceTask")
    return SliceTask(id="T", brief="do the thing", files=["src/x.py"],
                     acceptance_test_path="tests/test_x.py")


def _envelope(response="DONE", status="SUCCESS", **extra):
    body = {"conversation_id": "c0ffee00-0000-0000-0000-000000000000", "status": status,
            "response": response, "duration_seconds": 1.0, "num_turns": 1,
            "usage": {"input_tokens": 10, "output_tokens": 2, "thinking_tokens": 3,
                      "cache_read_tokens": 4, "total_tokens": 19}}
    body.update(extra)
    return json.dumps(body)


class _Runner:
    """Fake agy: answers the dispatch with stdout, and git capture_diff calls."""

    def __init__(self, stdout, *, rc=0, diff="DIFF", names="src/x.py\0"):
        self.stdout, self.rc, self.diff, self.names, self.calls = stdout, rc, diff, names, []

    def __call__(self, args, cwd, **_options):
        self.calls.append((list(args), cwd))
        joined = " ".join(args)
        if "-p" in args and "--add-dir" in args:
            return (self.rc, self.stdout)
        if "--name-only" in joined:
            return (0, self.names)
        if "diff" in joined:
            return (0, self.diff)
        return (0, "")


def _dispatch_argv(runner):
    return next(argv for argv, _ in runner.calls if "-p" in argv and "--add-dir" in argv)


def test_dispatch_requests_json_output(tmp_path):
    runner = _Runner(_envelope())
    _executor(runner=runner, model="Gemini 4 Argon (High)", home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    argv = _dispatch_argv(runner)
    assert "--output-format" in argv, argv
    assert argv[argv.index("--output-format") + 1] == "json", argv


def test_json_reply_and_token_usage_are_recorded(tmp_path):
    runner = _Runner(_envelope(response="DONE"))
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is True, res.raw_log
    assert "DONE" in res.raw_log
    assert res.diff == "DIFF" and res.files_changed == ["src/x.py"]
    assert res.token_usage == {"input": 10, "output": 2, "cache_read": 4, "total": 19}, res.token_usage


def test_json_error_status_is_a_failure_with_the_reason(tmp_path):
    runner = _Runner(_envelope(response="", status="ERROR", error="model exploded"))
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is False
    assert "model exploded" in res.raw_log


def test_empty_reply_keeps_the_worktree_changes(tmp_path):
    # The executor finished on a tool call with no closing prose, but edited files.
    runner = _Runner(_envelope(response=""), diff="REAL-DIFF")
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is True, res.raw_log
    assert res.diff == "REAL-DIFF" and res.files_changed == ["src/x.py"]


def test_no_reply_and_no_changes_is_still_malformed(tmp_path):
    runner = _Runner("not json at all", diff="", names="")
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is False
    assert (res.process or {}).get("error") == "malformed_output", res.process


def test_effort_is_passed_to_agy_only_when_given(tmp_path):
    with_effort = _Runner(_envelope())
    _executor(runner=with_effort, model="Gemini 4 Argon (High)", effort="high",
              home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    argv = _dispatch_argv(with_effort)
    assert "--effort" in argv and argv[argv.index("--effort") + 1] == "high", argv

    without = _Runner(_envelope())
    _executor(runner=without, model="Gemini 4 Argon (High)", home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert "--effort" not in _dispatch_argv(without)


def test_agy_on_path_wins_over_the_old_local_install(tmp_path, monkeypatch):
    agy_cmd = resolve(PROVIDER_MODULE, "_agy_cmd")
    old = tmp_path / "local" / "agy" / "bin"
    old.mkdir(parents=True)
    (old / "agy.exe").write_bytes(b"")
    monkeypatch.delenv("AGY_CMD", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    on_path = str(tmp_path / "home" / ".gemini" / "bin" / "agy.exe")
    monkeypatch.setattr("shutil.which", lambda name, *a, **k: on_path if name == "agy" else None)
    assert agy_cmd() == on_path
    monkeypatch.setenv("AGY_CMD", "custom-agy")
    assert agy_cmd() == "custom-agy"


def test_success_with_no_reply_and_no_uncommitted_changes_defers_to_candidate_check(tmp_path):
    # Codex review P2: the executor may have committed its work, so the worktree diff
    # against HEAD is empty. agy reported SUCCESS, so the dispatch completed; the
    # candidate check (which compares against the dispatch base) decides, as for opencode.
    runner = _Runner(_envelope(response=""), diff="", names="")
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is True, res.raw_log
    assert (res.process or {}).get("error") != "malformed_output", res.process


def test_error_status_keeps_the_reported_token_usage(tmp_path):
    # Codex review P2: usage spent on a failed dispatch is known, not unknown.
    runner = _Runner(_envelope(response="", status="ERROR", error="tool failed"))
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is False
    assert res.token_usage == {"input": 10, "output": 2, "cache_read": 4, "total": 19}, res.token_usage


def test_nonzero_exit_keeps_the_reported_token_usage(tmp_path):
    runner = _Runner(_envelope(response="", status="ERROR", error="boom"), rc=1)
    res = _executor(runner=runner, home=str(tmp_path)).run(_task(), str(tmp_path / "wt"))
    assert res.ok is False
    assert res.token_usage == {"input": 10, "output": 2, "cache_read": 4, "total": 19}, res.token_usage
