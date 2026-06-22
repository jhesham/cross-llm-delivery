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
  rework stays local. A slice may carry one level of `## SUBSLICE:` children, each independently
  routed to its own executor/model/effort and run as ordered children of the parent.
- **Two verification regimes:** deterministic (pytest pass/fail + a diff rule) and behavioral
  (Claude-as-judge G-Eval, for quality that `==` can't capture).
- **Resumable:** progress is persisted to a JSON ledger, so a stopped build resumes where it left off.
- **Observable:** each dispatch emits a Langfuse span (best-effort; no-op without keys).
- **Pluggable executor + model picker:** the proven Gemini workhorse is the default; an **OpenCode**
  adapter exposes a catalog of additional models (deepseek, kimi, claude, gpt, …). An interactive
  picker (or the `--executor name:model` flag) chooses per build, with cost-confirmation on metered
  models and a validate-before-trust step for untested ones.

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

3. **Run it — one DAG layer at a time (recommended):**

   ```bash
   python skill/scripts/run_delivery.py path/to/plan.md --repo . --step
   ```

   `--step` runs only the next pending layer (independent slices fan out concurrently in
   isolated worktrees), then exits with a gate code: **0** = layer all-passed (re-invoke for
   the next), **2** = some slices failed/deferred (inspect / retry / edit / skip), **3** =
   build complete. Re-invoking advances automatically — the ledger is the state — so this is
   resumable and keeps the orchestrator's context small between layers.

   To run the whole plan in one shot instead, drop `--step` and pass `--workers N`.

   Re-run either form to resume — already-done slices are skipped via the ledger.

   **Choosing the executor/model.** Omit `--executor` and (on a TTY) you get an interactive
   picker — the proven Gemini workhorse is the default; `Browse all models…` opens a unified
   drill-down index across executors (executor → provider → model → effort, with search and a
   headless-only filter). Or pass it explicitly: `--executor gemini`, `--executor gemini:<model-id>`,
   `--executor opencode:<provider/model>`, or `--executor cursor:<model>` (optionally with an
   `@effort` suffix). A per-slice `executor:` tag in the plan overrides the build default for that
   one slice. `--per-slice-pick` re-prompts at each slice (default is pick-once-and-stick).
   `--usage` prints a combined usage table (this build's ledger + OpenCode/Cursor account info)
   and exits.

### As a Claude Code skill

The `skill/` directory is a self-contained Claude Code skill. Point Claude Code at it (or package
it with `skill-creator`) and trigger it with a plan — Claude handles decomposition and judging,
the skill drives the executor.

---

## Configuration

| Knob | Where | Default |
|---|---|---|
| Executor / model | `--executor` (`gemini`, `gemini:<model>`, `opencode:<provider/model>`, `cursor:<model>`, optional `@effort`); interactive picker if omitted on a TTY | proven Gemini workhorse |
| Per-slice executor | `executor:` tag on a `## SLICE:` or `## SUBSLICE:` block (overrides the build default for that slice) | inherits build default |
| Re-pick each slice | `--per-slice-pick` | off (pick once, stick) |
| Workflow | `--step` (one DAG layer at a time) vs. whole-plan (`--workers N`) | — |
| Judge model (behavioral) | `cld.behavioral.make_compliance_metric(judge_model=...)` | `claude-sonnet-4-6` |
| Parallelism | `--workers` on `run_delivery.py` | 4 |
| Quota throttle | `run_plan_parallel(quota_check=, quota_threshold=)` | off / 95 |
| Ledger path | `--ledger` | `.cld-ledger.json` |
| Usage report | `--usage` (ledger + OpenCode account stats; no dispatch) | — |

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
dependency). Three executors ship today, all live-validated headless:
- **Antigravity** (`antigravity:<model>`) — the default workhorse (`antigravity:Gemini 3.1 Pro (High)`,
  flat-rate); also exposes Claude + GPT-OSS models.
- **OpenCode** (`opencode:<provider/model>`) — catalog + picker for deepseek/kimi/claude/gpt/… ;
  has free-tier models for $0 runs.
- **Cursor** (`cursor:<model>`, including Composer via `cursor:composer-2.5`) — wired end-to-end;
  long-prompt headless dispatch works via direct-node on Windows.

The executor registry takes further drop-in adapters (one `cld_providers/<name>/` package each).

---

## Per-provider skills

This monorepo is the single source for the engine and all provider adapters. It ships a
**generator** that produces self-contained, per-provider Claude Code skills — one skill per
executor backend (`cross-llm-antigravity`, `cross-llm-opencode`, `cross-llm-cursor`, …). Each
generated skill requires no `pip install` and carries only the provider code it needs.

> The old unified multi-provider skill (`skill/`) is **superseded** by the per-provider skills
> described here. New installs should use the per-provider workflow below.

### Generate a skill

Live providers: **antigravity** (default workhorse), **opencode**, **cursor**.

```bash
# one provider
python generator/build_skill.py antigravity

# all providers at once
python generator/build_skill.py --all
```

Each run writes a self-contained skill to `dist/cross-llm-<provider>/` (vendored engine +
provider adapter + references + composed `SKILL.md`). No pip install is needed inside the
generated skill — the engine is vendored into `scripts/cld/`.

**`dist/` is gitignored build output — always regenerate it; never rely on a checked-out copy.**
The one-shot clean rebuild is `pwsh ./rebuild-skills.ps1` (wipes `dist/` then runs `--all`).
For install steps on a fresh machine, see [INSTALL.md](INSTALL.md).

### Install a provider skill

Copy the generated folder into your Claude Code skills directory:

```bash
# macOS / Linux
cp -r dist/cross-llm-antigravity ~/.claude/skills/cross-llm-antigravity

# Windows (PowerShell)
Copy-Item -Recurse dist\cross-llm-antigravity "$env:USERPROFILE\.claude\skills\cross-llm-antigravity"
```

Alternatively, install directly from a published mirror repo (one repo per provider, tagged
`v<VERSION>`) or from the `cross-llm-all` umbrella (bundles every provider as subdirectories).

### Publish to mirror repos

`generator/publish.py` pushes each generated skill to its own remote mirror repo and tags the
commit. Dry-run by default; pass `--execute` to push for real.

```bash
# preview what would be pushed (no network)
python generator/publish.py

# push to all mirrors + the umbrella (requires publish-targets.toml)
python generator/publish.py --execute
```

Configure targets in `publish-targets.toml` (gitignored; copy from
`generator/publish-targets.example.toml`):

```toml
gemini  = "git@github.com:you/cross-llm-gemini.git"
opencode = "git@github.com:you/cross-llm-opencode.git"
cursor  = "git@github.com:you/cross-llm-cursor.git"
all     = "git@github.com:you/cross-llm-all.git"
```

---

## License

MIT — see [LICENSE](LICENSE).
