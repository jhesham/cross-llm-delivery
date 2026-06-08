# Phase 0 — Smoke Test Verdict

**Date:** 2026-06-08
**Slice:** `classify_node` (LangGraph-style node with injectable model boundary)
**Executor:** Gemini 3.1 Pro (`gemini-3.1-pro-preview`) via Gemini CLI 0.45.2, headless, native Windows.

## Result: ✅ GO

### Acceptance tests (judged by Claude, not self-reported)
- Claude ran `python -m pytest -v` independently → **2 passed**.
- Git status: **only** `classify_node.py` created; `tests/` and `state.py` untouched (executor honored "do not edit tests or state.py").

### Design-rule review of the produced diff
```python
from agent.state import State, ModelClient

def classify_node(state: State, model: ModelClient) -> State:
    prompt = state.get("text", "")
    label = model.complete(prompt)
    new_state: State = {**state, "label": label}
    return new_state
```
- ✅ Model access ONLY through the injected `model` param (no hardcoded client/import) — **injectable boundary honored**.
- ✅ Does not mutate input: returns a new dict via `{**state, ...}`.
- ✅ Imports contracts from `agent.state`.
- Minor (acceptable): used `state.get("text","")` instead of `state["text"]` — more defensive, harmless.
- **Quality grade: A.** Clean, minimal, idiomatic, contract-correct on the first dispatch.

### Cost (from `-o json` stats, `gemini-3.1-pro-preview`)
- API requests: 5 (0 errors); tool calls: 7 (read_file ×2, write_file ×1, run_shell_command ×1, update_topic ×3).
- Tokens: total **45,162** (input 32,575 / prompt 43,944 / output candidates **498** / cached 11,369 / thoughts 720). Lines: +8.
- **Caveat:** 45k tokens for an 8-line function is dominated by fixed overhead (workspace scan + system prompt + file reads); output was only 498 tokens. On a toy slice, overhead swamps signal. **The "~10× cheaper" cost premise is NOT validated by this slice** — it requires a representative-size slice to amortize the per-dispatch overhead. What IS proven here is the *loop mechanics and quality*.

## What this proves
1. Gemini CLI runs headless on native Windows (no WSL) and self-iterates (ran pytest itself).
2. Driven from a spec + failing test, it produces a clean, contract-correct slice.
3. Claude's independent judge loop (run tests + review diff vs design rule) works end-to-end.

## Operational learnings for the executor adapter
- Headless YOLO is **ignored unless the workspace is trusted**: set `GEMINI_CLI_TRUST_WORKSPACE=true` (or `--skip-trust`) AND pass `--yolo` (or `--approval-mode`). Adapter must set both.
- CLI emits harmless stderr warnings (256-color, ripgrep-missing) — ignore.
- `-o json` `stats.models.<id>.tokens` is the per-dispatch cost signal; capture it every run.
- Locked executor invocation:
  `GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<task>" -m gemini-3.1-pro-preview --yolo --skip-trust -o json`

## Next
GO to Phase 1 (project scaffold + verification harness). **Carry forward:** measure cost on a
real, representative-size slice early in Phase 1 to validate the cost premise before scaling.
