"""T5.6: behavioral-eval smoke test — Claude-as-judge G-Eval (no OpenAI).

The *intelligence* verification regime (design doc): non-deterministic, LLM-as-judge.
Marked `eval` and excluded from the default `pytest` run, which stays fast/offline.
Run the live judge with `pytest -m eval` (needs ANTHROPIC_API_KEY — NOT OpenAI).

This exercises cld.behavioral.evaluate_compliance with the real Claude judge: it scores
a trivially-compliant code sample against a tiny spec and asserts a passing score.
"""

import os

import pytest

pytestmark = pytest.mark.eval


def test_behavioral_eval_smoke_claude_judge():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set; Claude-judge behavioral eval skipped")

    from cld.behavioral import evaluate_compliance

    spec = "Write a function add(a, b) that returns the sum of a and b."
    code = "def add(a, b):\n    return a + b\n"
    result = evaluate_compliance(spec, code)  # real Claude judge via G-Eval
    assert result.score >= 0.5
    assert isinstance(result.reason, str)
