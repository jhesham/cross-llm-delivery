"""Tests for the run_delivery.py driver's --executor parsing (BUG 2 fix).

The user picks the LLM at invocation via --executor "name" or "name:model".
parse_executor_spec is pure, so we test it directly without invoking the CLI.
"""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "skill" / "scripts" / "run_delivery.py"
_spec = importlib.util.spec_from_file_location("run_delivery", _SCRIPT)
run_delivery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_delivery)
parse_executor_spec = run_delivery.parse_executor_spec


def test_bare_name():
    assert parse_executor_spec("gemini") == ("gemini", {})


def test_name_with_model():
    assert parse_executor_spec("gemini:gemini-3-pro-preview") == (
        "gemini", {"model": "gemini-3-pro-preview"})


def test_default_when_empty():
    assert parse_executor_spec("") == ("gemini", {})


def test_strips_whitespace():
    assert parse_executor_spec("  gemini : model-x ") == ("gemini", {"model": "model-x"})


def test_other_executor_name():
    # forward-compatible with the future opencode executor
    assert parse_executor_spec("opencode:anthropic/claude") == (
        "opencode", {"model": "anthropic/claude"})


def test_colon_with_no_model_is_no_kwargs():
    assert parse_executor_spec("gemini:") == ("gemini", {})


# ---- Bug B: pytest_test_runner scopes to the slice's acceptance test ----

def test_pytest_test_runner_scopes_to_acceptance_path(monkeypatch):
    captured = {}

    class _Proc:
        stdout = "1 passed in 0.0s"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["cwd"] = kwargs.get("cwd")
        captured["timeout"] = kwargs.get("timeout")
        return _Proc()

    monkeypatch.setattr(run_delivery.subprocess, "run", fake_run)
    out = run_delivery.pytest_test_runner("/wt", "tests/test_merge.py")
    assert "1 passed" in out
    # the acceptance path is in the argv; it is NOT a bare whole-suite run
    assert "tests/test_merge.py" in captured["argv"]
    assert captured["cwd"] == "/wt"
    assert captured["timeout"]  # a timeout guard is set


def test_pytest_test_runner_splits_test_selector(monkeypatch):
    # Shared accumulating test files need per-slice scoping: an acceptance_test_path
    # like "tests/test_x.py::test_one" (or with -k) must be split into SEPARATE argv
    # tokens so pytest applies the node id / -k expr — not passed as one malformed arg.
    captured = {}

    class _Proc:
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(run_delivery.subprocess, "run",
                        lambda argv, **kw: captured.update(argv=argv) or _Proc())

    run_delivery.pytest_test_runner("/wt", "tests/test_advisor_graph.py::test_merge_dict_reducer")
    assert "tests/test_advisor_graph.py::test_merge_dict_reducer" in captured["argv"]

    run_delivery.pytest_test_runner("/wt", 'tests/test_advisor_graph.py -k "merge"')
    argv = captured["argv"]
    # the path, the -k flag, and the expression are three distinct argv tokens
    assert "tests/test_advisor_graph.py" in argv
    assert "-k" in argv
    assert "merge" in argv  # quotes stripped by shlex, expression is its own token


def test_pytest_test_runner_without_path_runs_default(monkeypatch):
    # backward-compatible: no path -> runs pytest with no explicit target (still scoped
    # by cwd), and must not crash.
    class _Proc:
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(run_delivery.subprocess, "run", lambda argv, **kw: _Proc())
    assert "passed" in run_delivery.pytest_test_runner("/wt")
