"""T1.3: deepeval behavioral-eval smoke test.

This is the *intelligence* verification regime (see design doc): non-deterministic,
LLM-as-judge. It is marked `eval` and excluded from the default `pytest` run, which
stays fast/offline. Run it with `pytest -m eval` (needs OPENAI_API_KEY).
"""

import os

import pytest

pytestmark = pytest.mark.eval


def test_eval_smoke():
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; deepeval LLM-judge eval skipped")

    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase

    tc = LLMTestCase(input="say hi", actual_output="hi there")
    metric = AnswerRelevancyMetric(threshold=0.1)
    metric.measure(tc)
    assert metric.score >= 0.1
