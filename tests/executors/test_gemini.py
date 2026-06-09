"""T2.2: GeminiExecutor adapter — unit-tested with a mocked runner (no live calls).

The adapter wraps the locked Gemini CLI invocation, parses stats.models.*.tokens
into ExecutorResult.token_usage, and captures the diff via git. All subprocess
access goes through an injected `runner` so these tests never touch the network
or the real CLI.
"""

import json

from cld.executors.base import Executor, ExecutorResult, SliceTask
from cld.executors.gemini import GeminiExecutor, parse_token_usage


# A trimmed JSON in the exact shape the real `gemini -o json` emits
# (keys verified against the captured Phase-0 / gate fixtures).
SAMPLE_JSON = json.dumps(
    {
        "session_id": "abc",
        "response": "done",
        "stats": {
            "models": {
                "gemini-3.1-pro-preview": {
                    "tokens": {
                        "input": 44987,
                        "prompt": 50727,
                        "candidates": 578,
                        "total": 52188,
                        "cached": 5740,
                        "thoughts": 883,
                        "tool": 0,
                    }
                }
            }
        },
    }
)


# ---- parse_token_usage (pure) ----

def test_parse_token_usage_sums_across_models():
    usage = parse_token_usage(SAMPLE_JSON)
    assert usage["total"] == 52188
    assert usage["input"] == 44987
    assert usage["output"] == 578  # candidates -> output
    assert usage["cached"] == 5740


def test_parse_token_usage_handles_garbage():
    assert parse_token_usage("not json") == {}
    assert parse_token_usage("{}") == {}


def test_parse_token_usage_multiple_models_sums():
    blob = json.dumps(
        {
            "stats": {
                "models": {
                    "a": {"tokens": {"total": 10, "input": 6, "candidates": 4}},
                    "b": {"tokens": {"total": 20, "input": 15, "candidates": 5}},
                }
            }
        }
    )
    usage = parse_token_usage(blob)
    assert usage["total"] == 30
    assert usage["input"] == 21
    assert usage["output"] == 9


# ---- GeminiExecutor.run (mocked runner) ----

class RecordingRunner:
    """Injected in place of subprocess. Returns canned (rc, stdout) per call,
    matched by a substring of the command, and records every argv it saw."""

    def __init__(self, responses):
        # responses: list of (match_substr, rc, stdout)
        self._responses = responses
        self.calls = []

    def __call__(self, args, cwd):
        self.calls.append((args, cwd))
        joined = " ".join(args)
        for match, rc, out in self._responses:
            if match in joined:
                return (rc, out)
        return (0, "")


def _runner_ok(diff="--- a\n+++ b\n+x\n"):
    # NOTE: matched by first substring hit, so list more specific patterns first
    # ("--name-only" before the generic "diff", which would otherwise shadow it).
    return RecordingRunner(
        [
            ("gemini", 0, SAMPLE_JSON),            # the dispatch
            ("--name-only", 0, "src/cld/x.py\n"),  # changed files (specific first)
            ("diff", 0, diff),                     # git diff (generic last)
        ]
    )


def test_gemini_executor_satisfies_protocol():
    ex = GeminiExecutor(runner=_runner_ok())
    assert isinstance(ex, Executor)


def test_gemini_run_builds_locked_argv():
    runner = _runner_ok()
    ex = GeminiExecutor(runner=runner, model="gemini-3.1-pro-preview")
    task = SliceTask(id="T", brief="do the thing", files=["src/cld/x.py"],
                     acceptance_test_path="tests/test_x.py")
    ex.run(task, "/work")
    dispatch_argv = runner.calls[0][0]
    joined = " ".join(dispatch_argv)
    # locked invocation form (the proven one): -p, model, --yolo, --skip-trust, -o json
    assert "gemini" in dispatch_argv
    assert "-p" in dispatch_argv
    assert "gemini-3.1-pro-preview" in dispatch_argv
    assert "--yolo" in dispatch_argv
    assert "--skip-trust" in dispatch_argv
    assert "-o" in dispatch_argv and "json" in dispatch_argv
    # the brief is passed into the prompt
    assert "do the thing" in joined
    # ran in the given workdir
    assert runner.calls[0][1] == "/work"


def test_gemini_run_parses_tokens_and_diff():
    ex = GeminiExecutor(runner=_runner_ok(diff="DIFFCONTENT"))
    task = SliceTask(id="T", brief="b", files=["src/cld/x.py"],
                     acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert isinstance(res, ExecutorResult)
    assert res.ok is True
    assert res.token_usage["total"] == 52188
    assert res.token_usage["output"] == 578
    assert res.diff == "DIFFCONTENT"
    assert res.files_changed == ["src/cld/x.py"]
    assert res.raw_log == SAMPLE_JSON


def test_gemini_run_nonzero_dispatch_is_not_ok():
    runner = RecordingRunner([("gemini", 1, "boom error on stderr")])
    ex = GeminiExecutor(runner=runner)
    task = SliceTask(id="T", brief="b", files=["x"], acceptance_test_path="t.py")
    res = ex.run(task, "/work")
    assert res.ok is False
    assert "boom" in res.raw_log
