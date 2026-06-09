# cross-llm-delivery (`cld`)

**Route the bulk implementation of a large software build to a cheap headless executor LLM
(Gemini 3.1 Pro), while Claude acts as architect and judge.**

The expensive model does the *thinking* — decompose a build into vertical slices, fix the
interface contracts, write the acceptance tests, judge each result. A cheap headless executor
does the *typing* — implement each slice to make its tests pass. On a flat-rate executor plan
the typing is effectively free, so you pay only for the high-leverage spec + judge work.

> **For large builds only.** The per-dispatch overhead (workspace scan + spec) means
> orchestration is a net loss on small fixes. Small work stays with the expensive model directly.

---

## How it works

```
plan (slices + contracts + acceptance tests + dependency DAG)
        │
        ▼
  for each slice:  isolate (git worktree) → dispatch to executor → run pytest
                   → judge against acceptance tests → record to ledger
        │
  independent slices (per the DAG) run in PARALLEL in separate worktrees
        │
  after a batch merges → integration gate (full suite on the merged tree)
```

- **Vertical slices**, each independently testable, with stable contracts so a bad slice's
  rework stays local.
- **Two verification regimes:** deterministic (pytest pass/fail + a diff rule) and behavioral
  (Claude-as-judge G-Eval, for quality that `==` can't capture).
- **Resumable:** progress is persisted to a JSON ledger, so a stopped build resumes where it left off.
- **Observable:** each dispatch emits a Langfuse span (best-effort; no-op without keys).
- **Pluggable executor:** Gemini today; the registry takes drop-in adapters (a Composer stub ships
  as the worked example).

---

## Prerequisites

1. **Python ≥ 3.11.**
2. **The Gemini CLI**, installed and authenticated:
   ```bash
   npm install -g @google/gemini-cli
   gemini -p "say hello"   # should return output, confirming auth
   ```
   The executor runs headless and needs the workspace trusted — `cld` sets
   `GEMINI_CLI_TRUST_WORKSPACE=true` and passes `--yolo --skip-trust` for you.
3. **Git** (worktree isolation runs `git worktree add/remove`).
4. *Optional:* `ANTHROPIC_API_KEY` to enable behavioral (G-Eval) judging; `LANGFUSE_PUBLIC_KEY` /
   `LANGFUSE_SECRET_KEY` (+ optional `LANGFUSE_HOST`) to enable trace emission. Both degrade to
   no-ops when absent — nothing breaks without them.

---

## Install

```bash
git clone <your-fork-url> cross-llm-delivery
cd cross-llm-delivery
python -m pip install -e ".[dev]"   # runtime + test deps
python -m pytest                     # should pass
```

---

## Quickstart

1. **Write a plan.** A markdown file with one block per slice (see
   `skill/examples/demo-plan.md` for a worked example):

   ```
   ## SLICE: T1
   brief: Implement <X> so that tests/test_x.py passes. <contract, constraints, allowed files.>
   files: src/x.py, tests/test_x.py
   acceptance_test_path: tests/test_x.py
   deps:

   ## SLICE: T2
   brief: Implement <Y> ...
   files: src/y.py
   acceptance_test_path: tests/test_y.py
   deps: T1
   ```

   Author the acceptance tests first (committed, failing) — they are the objective contract the
   executor is judged against. See `skill/references/authoring-plans.md` for how to write good slices.

2. **Preview the schedule** (no dispatch):

   ```bash
   python skill/scripts/run_delivery.py path/to/plan.md --dry-run
   ```

3. **Run it:**

   ```bash
   python skill/scripts/run_delivery.py path/to/plan.md --repo . --workers 4
   ```

   Re-run to resume — already-done slices are skipped via the ledger.

### As a Claude Code skill

The `skill/` directory is a self-contained Claude Code skill. Point Claude Code at it (or package
it with `skill-creator`) and trigger it with a plan — Claude handles decomposition and judging,
the skill drives the executor.

---

## Configuration

| Knob | Where | Default |
|---|---|---|
| Executor | `get_executor("gemini" \| "composer")` | `gemini` |
| Judge model (behavioral) | `cld.behavioral.make_compliance_metric(judge_model=...)` | `claude-sonnet-4-6` |
| Parallelism | `--workers` on `run_delivery.py` | 4 |
| Quota throttle | `run_plan_parallel(quota_check=, quota_threshold=)` | off / 95 |
| Ledger path | `--ledger` | `.cld-ledger.json` |

---

## Cross-platform notes

- The engine is **plain Python** (threads, dataclasses, subprocess) and runs on macOS, Linux, and
  Windows. The Gemini CLI is Node-based and also cross-platform (no WSL needed on Windows).
- `verify.ps1` is a PowerShell convenience wrapper for Windows. On macOS/Linux, run the equivalent
  directly: `python -m pytest`.
- Paths in examples are relative; nothing is tied to a specific machine.

---

## Project layout

```
src/cld/            the engine (executor, judge, orchestrator, ledger, dag, gate, ...)
skill/              the Claude Code skill (SKILL.md, scripts, references, examples)
tests/              the test suite
docs/superpowers/   design doc + master build plan
```

## Status

The engine and skill are complete and tested. The behavioral-eval judge uses Claude (no OpenAI
dependency). Executor adapters beyond Gemini are a documented extension point (see the Composer
stub and `docs/notes/opencode-executor-option.md`).

## License

MIT — see [LICENSE](LICENSE).
