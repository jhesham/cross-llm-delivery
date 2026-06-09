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
