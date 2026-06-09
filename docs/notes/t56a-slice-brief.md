# T5.6a slice brief — Behavioral G-Eval wrapper (Claude-as-judge, no OpenAI)

Implement `src/cld/behavioral.py` so `tests/test_behavioral.py` passes. Only create that file.
Do NOT modify the test file. stdlib + deepeval imports only.

## Purpose

The behavioral-verification regime: when a slice produces non-deterministic output whose quality
can't be checked by `==`, score it with an LLM-as-judge. We use **Claude** as the judge (NOT
OpenAI) via deepeval's G-Eval, against a code-compliance rubric (does the produced code satisfy
the spec?).

## EXACT imports to use (verified in deepeval 4.0.5 — do NOT guess these)
```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase
from deepeval.test_case import LLMTestCaseParams  # INPUT, ACTUAL_OUTPUT live here
from deepeval.models import AnthropicModel        # the Claude judge class (NOT "AnthropicClaude")
```
Judge model string: **`claude-sonnet-4-6`** (current; do NOT use any `claude-3-5-...` string — retired).

## Contract (importable from `cld.behavioral`)

### `BehavioralResult` (dataclass)
- `score: float`
- `passed: bool`
- `reason: str` (default "")

### `make_compliance_metric(*, judge_model="claude-sonnet-4-6", threshold=0.8) -> GEval`
Build and return a `GEval` metric named "Architectural Compliance" with:
- `criteria`: "Assess whether the generated code satisfies every function, constraint, and
  error-handling requirement in the spec. Penalise missing functions or ignored constraints."
- `evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]`
- `model=AnthropicModel(model=judge_model, temperature=0.0)`
- `threshold=threshold`
(Constructing this must NOT make a network call — GEval/AnthropicModel construct lazily.)

### `evaluate_compliance(spec, code, *, metric=None) -> BehavioralResult`
- `spec`: the architectural/contract text (the INPUT). `code`: the produced code (ACTUAL_OUTPUT).
- If `metric is None`, build one via `make_compliance_metric()`.
- Build `LLMTestCase(input=spec, actual_output=code)`.
- Call `metric.measure(test_case)`.
- Return `BehavioralResult(score=metric.score, passed=metric.score >= metric.threshold,
  reason=getattr(metric, "reason", "") or "")`.
- The `metric` param is INJECTABLE so tests pass a fake metric (no live LLM / no API key needed).

## Design rules (judged by Claude)
- Use the EXACT imports above. Do not import OpenAI anything. Do not use `AnthropicClaude`.
- `evaluate_compliance` must work with an injected fake `metric` (duck-typed: has `.measure(tc)`,
  `.score`, `.threshold`, `.reason`) — so the test runs with NO network and NO API key.
- `make_compliance_metric` must construct without a network call.
- Mutable dataclass defaults via `field(default_factory=...)` if any.

## Done
`python -m pytest tests/test_behavioral.py` passes (offline, no API key); full suite stays green.
