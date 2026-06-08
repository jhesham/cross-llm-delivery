# Cross-LLM Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route large agentic builds to a cheap executor LLM (Gemini 3.1 Pro) with Claude (Opus) as architect + judge, cutting Opus token cost while preserving engineering quality.

**Architecture:** Claude decomposes a build into vertical slices with interface contracts and per-slice acceptance tests (a dependency DAG). An orchestrator skill dispatches each slice to a headless executor CLI inside an isolated git worktree, then Claude judges the resulting diff against pytest/deepeval. Independent slices fan out in parallel; an integration gate validates merged results; a progress ledger makes the build resumable.

**Tech Stack:** Python, LangGraph, pytest, deepeval, Langfuse (self-hosted), Gemini CLI (Gemini 3.1 Pro), git worktrees, Claude Code skill.

**Staging note:** Phase 0 is a hard go/no-go gate. Only Phase 0 is fully detailed below. Phases 1–6 are a roadmap; each gets its own detailed writing-plans pass **after** Phase 0 validates the executor's quality/cost premise.

---

## Phase 0 — Executor Validation (Smoke Test) [GATE]

**Purpose:** Prove that Gemini CLI runs headless on this Windows machine, can be driven from a spec + failing test to produce a passing diff for a representative agentic slice, and that the quality/cost is good enough to justify the whole pipeline. **If this fails, the executor choice changes before any further build.**

**Representative slice chosen:** a single LangGraph-style node with an *injectable model client* that transforms state — because it exercises the core design rule (injectable boundary), the state-in/state-out contract, and a deterministic mocked-LLM test, which is exactly the pattern every real slice will use.

### Task 0.1: Install and verify Gemini CLI (Windows native, headless)

**Files:** none (environment setup)

- [ ] **Step 1: Install Gemini CLI**

Run (user may need to run interactively for auth):
```powershell
npm install -g @google/gemini-cli
```
Expected: global install completes; `gemini` on PATH.

- [ ] **Step 2: Verify binary + version**

Run: `gemini --version`
Expected: prints a version string (no "command not found").

- [ ] **Step 3: Authenticate**

Run `gemini` once interactively (Google account login or set `GEMINI_API_KEY`). Confirm a trivial prompt returns:
```powershell
gemini -p "reply with the single word: ready"
```
Expected: output contains `ready`.

- [ ] **Step 4: Confirm the model id and headless flags**

Run: `gemini --help` and (if supported) a model-list command.
Capture: exact model id for "Gemini 3.1 Pro", the prompt flag (`-p`/`--prompt`), model flag (`-m`/`--model`), auto-approve flag (`-y`/`--yolo`), and JSON output flag.
Expected: a documented headless invocation form, e.g. `gemini -p "<task>" -m <model-id> -y`. **Record the exact form in `docs/notes/gemini-cli.md`.**

### Task 0.2: Scaffold the smoke-test sandbox

**Files:**
- Create: `smoketest/pyproject.toml`
- Create: `smoketest/src/agent/state.py`
- Create: `smoketest/tests/test_classify_node.py`

- [ ] **Step 1: Create the Python project + deps**

`smoketest/pyproject.toml`:
```toml
[project]
name = "smoketest"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

- [ ] **Step 2: Define the state contract (the seam the executor must honor)**

`smoketest/src/agent/state.py`:
```python
from typing import TypedDict, Protocol


class ModelClient(Protocol):
    """Injectable model boundary — nodes must call models only through this."""
    def complete(self, prompt: str) -> str: ...


class State(TypedDict):
    text: str
    label: str
```

- [ ] **Step 3: Write the FAILING acceptance test (this is the spec we hand the executor)**

`smoketest/tests/test_classify_node.py`:
```python
from agent.state import State
from agent.classify_node import classify_node  # does not exist yet


class FakeModel:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


def test_classify_node_sets_label_from_model():
    model = FakeModel(reply="positive")
    state: State = {"text": "I love this", "label": ""}
    result = classify_node(state, model)
    assert result["label"] == "positive"
    assert result["text"] == "I love this"  # node must not mutate input text


def test_classify_node_passes_text_to_model():
    model = FakeModel(reply="negative")
    classify_node({"text": "bad", "label": ""}, model)
    assert any("bad" in p for p in model.calls)  # text reached the model via the boundary
```

- [ ] **Step 4: Verify deps install and the test FAILS for the right reason**

Run: `cd smoketest && pip install -e ".[dev]" && pytest -v`
Expected: collection/import error — `classify_node` does not exist. (Confirms the test is real and gates the executor.)

- [ ] **Step 5: Commit the sandbox + failing test**

```bash
git add smoketest
git commit -m "test: phase0 smoke-test sandbox with failing classify_node spec"
```

### Task 0.3: Author the executor task brief

**Files:** Create `smoketest/SLICE_BRIEF.md`

- [ ] **Step 1: Write the brief the executor receives (no solution, just contract + DoD)**

`smoketest/SLICE_BRIEF.md`:
```markdown
# Slice: classify_node
Create `src/agent/classify_node.py` defining:
`def classify_node(state: State, model: ModelClient) -> State`
- Import `State` and `ModelClient` from `agent.state`. Do NOT modify state.py.
- Build a prompt from `state["text"]`, call `model.complete(prompt)`, set the returned
  string as `label`. Return a new/updated State; do not mutate `text`.
- All model access MUST go through the injected `model` param (no hardcoded clients/imports).
Definition of Done: `pytest -v` passes all tests in tests/test_classify_node.py.
```

### Task 0.4: Dispatch the slice to Gemini CLI in isolation

**Files:** none (produces a branch + diff)

- [ ] **Step 1: Isolate in a worktree/branch**

```bash
cd /d/claude_server/cross-llm-delivery
git worktree add ../cld-smoke-exec -b smoke/classify-node
```

- [ ] **Step 2: Run the executor headless against the brief**

Run (use the exact form recorded in Task 0.1.4; example):
```powershell
cd D:\cld-smoke-exec\smoketest
gemini -p "Read SLICE_BRIEF.md and implement it. Run pytest until green. Do not edit tests or state.py." -m <gemini-3.1-pro-id> -y
```
Capture stdout/stderr **and any reported token usage** to `docs/notes/phase0-run.log`.

- [ ] **Step 3: Collect the diff**

Run: `cd /d/cld-smoke-exec && git add -A && git diff --cached --stat && git diff --cached`
Expected: a new file `src/agent/classify_node.py`; state.py and tests untouched.

### Task 0.5: Judge the result (Claude)

**Files:** Create `docs/notes/phase0-verdict.md`

- [ ] **Step 1: Run the acceptance tests**

Run: `cd /d/cld-smoke-exec/smoketest && pytest -v`
Expected: all tests PASS.

- [ ] **Step 2: Review the diff against the design rule**

Claude inspects the diff: did the executor (a) keep model access behind the injected boundary, (b) leave tests + state.py unmodified, (c) avoid mutating `text`? Note any violations even if tests pass.

- [ ] **Step 3: Record cost + quality**

In `docs/notes/phase0-verdict.md` capture: executor tokens used (from run log), wall-clock, # of executor iterations to green, contract violations, and a quality grade. Compare token cost vs. an estimate of Claude doing the same slice.

### Task 0.6: Go/No-Go decision

- [ ] **Step 1: Decide**

GO if: tests pass, design rule honored, and token cost is materially below Claude-equivalent. Otherwise NO-GO → revisit executor (try Composer/cursor-agent, or adjust briefing/model). Record the decision in `phase0-verdict.md` and update the design doc's "Open validation" line.

- [ ] **Step 2: Clean up worktree**

```bash
cd /d/claude_server/cross-llm-delivery
git worktree remove ../cld-smoke-exec --force
```

---

## Phases 1–6 — Roadmap (detailed-plan each AFTER Phase 0 = GO)

**Phase 1 — Project scaffold & verification harness.** Real project layout; pytest + deepeval wired into one `pytest` run; self-hosted Langfuse + tracing helper; CI-style `make verify`. *Output: a green walking skeleton.*

**Phase 2 — Executor adapter (pluggable).** Define the `(task + worktree) → diff` contract as a Python interface; implement the `GeminiExecutor` adapter wrapping the CLI form proven in Phase 0; stub interface for a future `ComposerExecutor`. *Output: one function Claude can call to run any executor.*

**Phase 3 — Orchestrator core (single-slice judge loop).** Given one slice spec + acceptance test: create worktree → dispatch via adapter → run verify → judge → iterate-or-accept → integrate. Sequential only. *Output: end-to-end single-slice delivery.*

**Phase 4 — Progress ledger (resumability).** Persisted ledger (slices done/pending/failed + DAG state) in the repo; orchestrator reads/writes it so a fresh session resumes mid-build.

**Phase 5 — Parallel fan-out + integration gate.** Execute DAG-independent slices in parallel worktrees; after each parallel batch merges, run the full suite as an integration gate (slice-green ≠ system-green).

**Phase 6 — The `cross-llm-delivery` skill.** Package the orchestrator as a Claude Code skill (via skill-creator) that consumes a writing-plans plan (slices + contracts + tests + DAG) and runs Phases 3–5. *Optional later:* enforcement hook for hard "all large-build implementation → executor" routing.

---

## Self-Review (Phase 0)

- **Spec coverage:** Phase 0 covers the design's "open validation" (Gemini quality/cost) and exercises the core design rule (injectable boundary), the slice/contract/acceptance-test pattern, worktree isolation, and the judge loop in miniature. Phases 1–6 map 1:1 to the design's pipeline, verification stack, adapter, baked-in integration gate (Phase 5) and resumable ledger (Phase 4).
- **Placeholders:** none in Phase 0 — real commands, real test code, real brief. `<gemini-3.1-pro-id>` and the exact headless flag form are intentionally resolved *by* Task 0.1 and recorded before use (not a placeholder, a step output).
- **Type consistency:** `State` (keys `text`, `label`) and `ModelClient.complete(prompt)->str` defined in 0.2 and used consistently in the test (0.2), brief (0.3), and judging (0.5).
