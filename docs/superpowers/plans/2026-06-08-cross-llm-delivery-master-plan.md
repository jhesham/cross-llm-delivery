# Cross-LLM Delivery — Master Build Plan (multi-sitting)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Route large agentic builds to a cheap executor LLM (Gemini 3.1 Pro) with Claude (Opus) as architect + judge, cutting Opus token cost while preserving quality.

**Architecture:** Claude decomposes a build into vertical slices (contracts + acceptance tests + dependency DAG). An orchestrator dispatches each slice to a headless executor CLI in an isolated git worktree, then Claude judges the diff against pytest/deepeval. Independent slices run in parallel; an integration gate validates merges; a progress ledger makes builds resumable. Packaged as a shareable Claude Code skill.

**Tech stack:** Python 3.13, LangGraph, pytest, deepeval, Langfuse (self-hosted), Gemini CLI (`gemini-3.1-pro-preview`), git worktrees, Claude Code skill.

---

## How to run this across many sittings (token-limit aware)

- **One task = one sitting unit.** Each task below is sized to complete + commit within a modest token budget. You may do several per sitting if budget allows, but **never leave a task half-done across a stop** — finish to a green commit.
- **Every task ends with:** (a) tests green, (b) `git commit`, (c) update `STATUS.md` (tick task, set "Next task", bump "Last updated"), (d) tick the checkbox here.
- **Every sitting starts with:** read `STATUS.md` → it names the next task. No re-derivation needed.
- **Phase 1 is fully detailed** below (next sittings). **Phases 2–6 are task-specs** (files + DoD + approach + deps); each gets a just-in-time bite-sized expansion at the *start of its sitting* — this is deliberate (their detail depends on earlier outcomes, and it keeps this doc from going stale). JIT expansion is appended to this file under the task before executing it.
- **Dogfooding note:** the resumability we hand-roll via `STATUS.md` now is the same capability the product builds in Phase 4. Once Phase 4 exists, the ledger becomes machine-managed.

---

## Phase 1 — Project scaffold & verification harness (detailed)

### T1.1 — Project scaffold + walking skeleton + verify script

**DoD:** `python -m pytest` green on a trivial skeleton test; `verify.ps1` runs it; committed.
**Files:**
- Create: `pyproject.toml`, `src/cld/__init__.py`, `src/cld/_skeleton.py`, `tests/test_skeleton.py`, `verify.ps1`

- [ ] **Step 1: pyproject with deps**

`pyproject.toml`:
```toml
[project]
name = "cld"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["langgraph>=0.2", "langfuse>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=8", "deepeval>=1.0"]

[tool.pytest.ini_options]
pythonpath = ["src"]
addopts = "-q"
```

- [ ] **Step 2: walking-skeleton module + failing test**

`src/cld/_skeleton.py`:
```python
def healthcheck() -> str:
    return "cld-ok"
```
`tests/test_skeleton.py`:
```python
from cld._skeleton import healthcheck

def test_healthcheck():
    assert healthcheck() == "cld-ok"
```

- [ ] **Step 3: verify script (the single command the judge runs)**

`verify.ps1`:
```powershell
param([string]$Path = ".")
python -m pytest $Path
exit $LASTEXITCODE
```

- [ ] **Step 4: install + run**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest`
Expected: 1 passed.

- [ ] **Step 5: commit + STATUS update**

```bash
git add -A && git commit -m "feat(T1.1): project scaffold + walking skeleton + verify"
```
Then tick T1.1 in STATUS.md, set Next task = T1.2, commit that.

### T1.2 — Langfuse tracing (self-hosted, with cloud fallback)

**DoD:** a `cld.tracing` helper emits a trace for a dummy span; a test asserts the client initializes; tracing target documented. Committed.
**Files:** Create `docs/notes/langfuse-setup.md`, `src/cld/tracing.py`, `tests/test_tracing.py`

- [ ] **Step 1: decide host.** Check Docker: `docker --version`. If present → self-host via Langfuse `docker-compose` (document compose + the 3 env vars: `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`). If Docker absent → use Langfuse Cloud free tier; record decision in `langfuse-setup.md`. **(This is a real fork — surface to the user if Docker is missing.)**

- [ ] **Step 2: tracing helper**

`src/cld/tracing.py`:
```python
import os
from functools import lru_cache
from langfuse import Langfuse

@lru_cache
def get_tracer() -> Langfuse:
    return Langfuse(
        host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    )
```

- [ ] **Step 3: test (no network — assert config wiring)**

`tests/test_tracing.py`:
```python
import os, importlib
def test_tracer_reads_env(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "http://x:3000")
    import cld.tracing as t; importlib.reload(t); t.get_tracer.cache_clear()
    tr = t.get_tracer()
    assert tr is not None
```

- [ ] **Step 4: run + commit + STATUS update** (`feat(T1.2): langfuse tracing helper`).

### T1.3 — deepeval behavioral-eval harness

**DoD:** a deepeval-based test runs under `python -m pytest` and passes on a trivial golden case (LLM-as-judge metric, mocked/threshold so it's deterministic-enough for CI). Committed.
**Files:** Create `tests/evals/test_eval_smoke.py`, `docs/notes/evals.md`

- [ ] **Step 1: write a minimal deepeval test**
```python
from deepeval.test_case import LLMTestCase
from deepeval.metrics import AnswerRelevancyMetric

def test_eval_smoke():
    tc = LLMTestCase(input="say hi", actual_output="hi there")
    metric = AnswerRelevancyMetric(threshold=0.1)
    metric.measure(tc)
    assert metric.score >= 0.1
```
(If deepeval requires an eval model/key, document it in `evals.md` and gate the test with `@pytest.mark.eval` so the default `pytest` run stays fast; evals run via `pytest -m eval`.)

- [ ] **Step 2: confirm both regimes run** — `python -m pytest` (structural, fast) and `python -m pytest -m eval` (behavioral). Document the two commands in `evals.md`.

- [ ] **Step 3: commit + STATUS update** (`feat(T1.3): deepeval harness + two-regime verify`).

### T1.4 — Cost-validation slice (validate the 10× premise) [PREMISE GATE]

**DoD:** one *representative-size* real slice (a 3–4 node LangGraph subgraph with injected model/tools + ~6 tests) built via Gemini using the Phase-0 invocation; tokens captured from `-o json`; compared to a Claude-equivalent estimate; verdict recorded. Committed.
**Files:** Create `docs/notes/cost-validation.md` (+ throwaway slice in a worktree, then removed)

- [ ] **Step 1:** Claude authors the slice spec + failing tests (representative size, not a toy).
- [ ] **Step 2:** worktree + dispatch via `GEMINI_CLI_TRUST_WORKSPACE=true gemini -p "<task>" -m gemini-3.1-pro-preview --yolo --skip-trust -o json`; capture token stats.
- [ ] **Step 3:** Claude judges (run verify + diff review); record executor tokens vs estimated Claude tokens for the same work in `cost-validation.md`.
- [ ] **Step 4: DECISION.** If cost advantage is real on representative work → continue. If not → reassess executor/model (try `gemini-3-pro-preview`, or Composer) before Phase 2. Record in `cost-validation.md` + STATUS.
- [ ] **Step 5:** remove worktree; commit notes (`docs(T1.4): cost-validation verdict`).

---

## Phase 2 — Executor adapter (task-specs; JIT-expand per task)

### T2.1 — Executor interface
**Deps:** T1.1. **Files:** `src/cld/executors/base.py`, `tests/executors/test_base.py`
**DoD:** `Executor` Protocol with `run(task: SliceTask, workdir: Path) -> ExecutorResult`; `ExecutorResult` dataclass (diff/files_changed, token_usage, raw_log, ok); unit test for the dataclass. No real CLI yet.

### T2.2 — GeminiExecutor adapter
**Deps:** T2.1, Phase 0 notes. **Files:** `src/cld/executors/gemini.py`, `tests/executors/test_gemini.py`
**DoD:** wraps the locked CLI form (env trust + `--yolo --skip-trust -o json`), parses `stats.models.*.tokens` into `token_usage`, returns diff via git. Unit-test by **mocking subprocess** (no live calls) — assert correct argv + parsing of a captured sample JSON (use the real Phase-0 JSON as fixture).

### T2.3 — Executor registry + Composer stub
**Deps:** T2.2. **Files:** `src/cld/executors/__init__.py`, `src/cld/executors/composer.py` (stub raising NotImplementedError), `tests/executors/test_registry.py`
**DoD:** `get_executor(name)` selects gemini|composer; Composer is a documented stub. Proves pluggability without building Composer.

---

## Phase 3 — Orchestrator core, single-slice loop (task-specs)

### T3.1 — Slice spec model
**Files:** `src/cld/plan/slice.py`, `tests/plan/test_slice.py`
**DoD:** `SliceTask` (id, brief, files, acceptance_test_path, deps[]) + loader from a plan markdown/YAML; round-trip test.

### T3.2 — Worktree manager
**Files:** `src/cld/worktree.py`, `tests/test_worktree.py`
**DoD:** context-manager that creates `git worktree add` on a branch and removes it on exit; integration test against a temp git repo (create→exists→cleanup).

### T3.3 — Judge module
**Files:** `src/cld/judge.py`, `tests/test_judge.py`
**DoD:** runs `verify.ps1`/pytest in a workdir, parses pass/fail + failing test names, returns `JudgeResult`; structural diff-rule checks (no edits outside allowed files). Test with a fake passing + fake failing dir.

### T3.4 — Single-slice loop
**Files:** `src/cld/orchestrator.py`, `tests/test_orchestrator_single.py`
**DoD:** `deliver_slice(task)` = worktree → executor.run → judge → (retry with feedback up to N) → accept+merge or fail. Sequential, one slice. Test with a **fake executor** that writes a known-good (and a known-bad) file; assert accept/merge vs fail-after-retries. (No live LLM in tests.)

---

## Phase 4 — Progress ledger / resumability (task-specs)

### T4.1 — Ledger schema
**Files:** `src/cld/ledger.py`, `tests/test_ledger.py`
**DoD:** JSON ledger (slice id → status done|pending|failed|in_progress, commit, attempts) with atomic read/write; round-trip + corruption-safe load tests.

### T4.2 — Resumable orchestrator
**Files:** modify `src/cld/orchestrator.py`, `tests/test_orchestrator_resume.py`
**DoD:** orchestrator reads ledger, skips done slices, persists after each; a simulated mid-build stop + fresh start resumes from the right slice. Replaces the hand-rolled `STATUS.md` for product builds.

---

## Phase 5 — Parallel fan-out + integration gate (task-specs)

### T5.1 — DAG scheduler
**Files:** `src/cld/dag.py`, `tests/test_dag.py`
**DoD:** topological layering from slice `deps[]`; detect cycles; yield parallelizable batches. Pure-function tests.

### T5.2 — Parallel fan-out
**Files:** modify `src/cld/orchestrator.py`, `tests/test_orchestrator_parallel.py`
**DoD:** run a batch's independent slices concurrently (separate worktrees), each judged; aggregate results. Test with fake executors + a small DAG.

### T5.3 — Integration gate
**Files:** `src/cld/integration_gate.py`, `tests/test_integration_gate.py`
**DoD:** after a batch merges, run full suite on merged tree; on failure, mark batch for rework. Test merged-green vs merged-red.

---

## Phase 6 — Skill packaging + sharing (task-specs)

### T6.1 — Package as Claude Code skill
**Deps:** Phases 2–5. **Approach:** use skill-creator. **Files:** `skill/` (SKILL.md + scripts wiring orchestrator).
**DoD:** a `cross-llm-delivery` skill that, given a writing-plans plan (slices+contracts+tests+DAG), runs Phases 3–5; smoke-tested on a small real plan end-to-end.

### T6.2 — Sharing docs/README
**DoD:** README (install, prereqs incl. Gemini CLI + trust env var, configuring executors, cross-platform notes for macOS/Linux), LICENSE, quickstart. Honors the "share much wider" intent — no machine-specific paths.

### T6.3 — (optional) Enforcement hook
**DoD:** opt-in PreToolUse hook that routes large-build implementation to the executor and keeps Claude as judge. Documented as optional/advanced.

---

## Self-Review
- **Spec coverage:** pipeline (T3.x), vertical-slice/contract model (T3.1), pluggable executor (T2.x), pytest+deepeval+Langfuse (T1.1–1.3), injectable-boundary rule (enforced in slice specs + T1.4), integration gate (T5.3), resumable ledger (T4.x), shareable skill (T6.x), cost premise (T1.4 gate). All design sections map to tasks.
- **Placeholders:** Phase 1 has real code/commands. Phases 2–6 are intentionally task-specs (JIT-expanded at execution) — flagged, not omissions.
- **Type consistency:** `SliceTask`/`ExecutorResult`/`JudgeResult`/ledger entry names are referenced consistently across T2–T5; concrete signatures get fixed at each task's JIT expansion and recorded here.
