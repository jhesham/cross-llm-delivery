# cross-llm-delivery (`cld`)

[![CI](https://github.com/jhesham/cross-llm-delivery/actions/workflows/ci.yml/badge.svg)](https://github.com/jhesham/cross-llm-delivery/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/jhesham/cross-llm-delivery)](https://github.com/jhesham/cross-llm-delivery/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Route the bulk implementation of a large software build to a cheap headless executor LLM,
while Claude acts as architect and judge — and let committed failing tests, not an LLM,
decide whether the cheap model's work merges.**

The expensive model does the *thinking* — decompose a build into vertical slices, fix the
interface contracts, write the acceptance tests, judge each result. A cheap headless executor
CLI does the *typing* — implement each slice to make its tests pass. On a flat-rate executor
plan the typing is effectively free, so you pay only for the high-leverage spec + judge work.

This is **not another model router** (the smart model stays in charge) and **not an AI
council** (no LLM votes on whether code is correct). Each slice ships with a
**committed, failing acceptance test**; the judge runs the real test suite in an isolated
git worktree and trusts the **exit code**. A diff rule rejects work that touches files
outside the slice's allowance. Failures retry with structured judge feedback, then escalate
up a model-cost ladder.

`cld` builds parts of itself this way: its telemetry subsystem and its executor preflight were
implemented by the cheap executors it orchestrates, each slice gated by acceptance tests written
and committed (failing) first — verifiable in this repo's history.

> **For large builds only.** The per-dispatch overhead (workspace scan + spec) means
> orchestration is a net loss on small fixes. Small work stays with the expensive model directly.

---

## How it works

```
plan (slices + contracts + committed failing acceptance tests + dependency DAG)
        │
        ▼
  for each slice:  isolate (git worktree) → dispatch to executor CLI → run pytest
                   → judge on the REAL exit code + allowed-files diff rule
                   → retry with judge feedback / escalate up the model ladder → ledger
        │
  independent slices (per the DAG) run in PARALLEL in separate worktrees
        │
  after a layer merges → integration gate (full suite on the merged tree)
```

- **Vertical slices**, each independently testable, with stable contracts so a bad slice's
  rework stays local. A slice may carry `## SUBSLICE:` children, each independently routed.
- **Deterministic judging:** the acceptance tests are authored and committed (failing) *before*
  dispatch. The judge runs them for real; pass/fail is the pytest exit code, never the
  executor's self-report and never another LLM's opinion. A second, optional behavioral regime
  (Claude-as-judge G-Eval) exists for qualities `==` can't capture.
- **Allowed-files enforcement:** a slice that edits outside its declared files is rejected,
  even if its tests pass — this is what stops a confused executor from rewriting your deps.
- **Escalation ladder:** untagged slices route by complexity to the cheapest viable model and
  climb (cheap → workhorse → heavy) on failure; every switch is recorded with its reason.
- **Resumable:** progress persists to a JSON ledger; a stopped build resumes where it left off.
- **Observable:** every lifecycle moment emits a structured event to `.cld/events.jsonl`;
  `--status` prints a compact digest (layer position, in-flight slices + elapsed, tokens,
  **cost by model**, gate) and `--watch` repaints it live. Opt-in OpenTelemetry export sends
  the same events to any OTLP backend (Phoenix, Langfuse, Grafana, Honeycomb) — see
  [skill/references/observability.md](skill/references/observability.md).

## What driving it looks like

Real output, unedited, from builds of this repo and a 16-slice application build. Each `--step`
runs one DAG layer and exits with a gate code the orchestrator (or you) acts on:

```
LAYER 1 of 2  --  done
  S1  + pass   1 file (+75)   attempt 1
GATE: 1 passed, 0 failed, 0 need repair.
NEXT: layer 2 -> [S2]
```

At any point, `--status` reconstructs live build state from the telemetry stream — including
**which model ran which slice, why, and what it cost** (flat-rate rows show $0.00; the metered
detour is attributed exactly):

```
cld status - run cc695749  (CLD_PLAN.md)
layer 2/6  done: 1  pending: 0  running: 0  tokens: 1271830  cost: $0.24
by model:
  cursor:composer-2.5  slices: T5,T2,T8,T3,T4,T10,T15,T17,T11,T9,T7,T6  tokens: 678694  cost: $0.00  source: default
  opencode:opencode/deepseek-v4-pro  slices: T15  tokens: 593136  cost: $0.24  source: default
gate: --
```

## The design stance

There are many good ways to combine models — routers that swap the assistant's backend for a
cheaper one, consultation servers that gather second opinions across models, multi-agent suites
that coordinate whole swarms. `cld` makes four narrower choices:

- **The smart model never leaves the loop.** Claude decomposes the build, fixes the contracts,
  and judges every result — only the implementation typing is delegated to the cheap executor.
- **Tests are the judge, not an LLM.** Every slice's acceptance test is committed — failing —
  *before* dispatch. The merge gate is the real pytest exit code plus an allowed-files diff
  rule; no model's opinion decides whether work is accepted.
- **Failure has a protocol.** Judge feedback feeds the retry; persistent failure climbs a
  model-cost ladder; every dispatch, verdict, and model switch is recorded in a local telemetry
  stream you can poll (`--status`).
- **Narrow on purpose.** `cld` is a delivery pipeline, not a platform — one pattern
  (plan → dispatch → judge → merge), done deterministically, designed to slot into whatever
  workflow you already run.

## Safety rails (what happens when the cheap model goes wrong)

Delegation is only as good as its guardrails. These all exist because something went wrong in a
real build and the rail caught it:

- **Allowed-files rejection.** A slice that edits files outside its declared allowance is
  rejected *even if its tests pass*. (Live case: an executor hit missing dependencies in its
  isolated worktree and "helpfully" rewrote 12 dependency files — tests green, diff rejected.)
- **Nothing is lost on rejection.** A rejected slice's full diff is preserved to
  `.cld/<slice>/<slice>.patch` before its worktree is removed — recoverable with `git apply`.
- **Judge verdicts are auditable.** Every attempt's raw pytest output is saved to
  `.cld/<slice>/judge-output.txt`, so a rejection is never a mystery.
- **Preflights, not tracebacks.** Before dispatching, `cld` checks the executor CLI actually
  resolves (friendly message + installed alternatives if not) and warns loudly if a pending
  layer depends on accepted-but-unmerged slice branches (the dep-blind-worktree trap).
- **Escalation is bounded and visible.** A failing slice retries with judge feedback, then
  climbs the model ladder; every switch is a telemetry event with its reason (`source`).

## Providers & models

Three executor providers ship today. Each carries a vendored catalog with a **cost class** and a
**validation status** — `cld` won't quietly trust an unproven model: uncatalogued or untested
models get a **validate-before-trust probe** (one trivial slice, judged for real) before a build
commits to them, with outcomes recorded in a local evidence store
(`~/.cld/validation-evidence.json`).

| Provider | Cost model | Catalog highlights | Proven in real builds¹ |
|---|---|---|---|
| **antigravity** (`agy`) | flat-rate (Google AI sub) | Gemini 3.1 Pro (default workhorse), Gemini 3.5 Flash tiers, Claude Sonnet/Opus (Thinking), GPT-OSS 120B | Gemini 3.1 Pro (High) |
| **opencode** | free tier + cheap/premium metered | deepseek-v4 (incl. a **free** tier), kimi-k2.7-code, GLM-5.x², Gemini 3.1 Pro, Claude Sonnet/Opus | kimi-k2.7-code, deepseek-v4-pro, gemini-3.1-pro, GLM-5.2 |
| **cursor** | subscription | composer-2.5 | composer-2.5 (16-slice application build) |

¹ *"Proven" = accepted real slices in live builds during this tool's development (real pytest
gates, worktree isolation) — including the dogfood builds where these executors implemented parts
of `cld` itself. Validation statuses live in a machine-local evidence store; on your machine, the
validate-before-trust probe re-establishes them automatically.*
² *Uncatalogued models (e.g. `opencode/glm-5.2`) are usable via an explicit per-slice `executor:`
tag; the probe covers them too.*

New providers are drop-in: one `cld_providers/<name>/` package (catalog + executor + skill
fragment) — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Is this for you?

- ✅ **Yes** — if your build is big enough to decompose into vertical slices whose acceptance
  can be expressed as committed tests, and you're paying for (or can get) one of the executor
  CLIs anyway.
- ❌ **No** — for small fixes and one-file changes: the per-dispatch overhead outweighs the
  savings. Keep those with your main assistant.
- ❌ **No** — if the work's acceptance can't be captured in tests (pure exploration, visual
  polish, "make it feel nicer"): the deterministic judge would have nothing to hold, and the
  optional Claude-as-judge behavioral regime is a complement, not a substitute.

---

## Prerequisites

1. **Python ≥ 3.11** and **git** (worktree isolation runs `git worktree add/remove`).
2. **[Claude Code](https://claude.com/claude-code)** — the output of this repo is a Claude Code
   *skill*; Claude is the architect/judge that drives it.
3. **At least one executor CLI** (Node/npm-based; install the one whose plan you already pay for):
   - **OpenCode** (`npm install -g opencode-ai`) — model catalog incl. free-tier models for $0
     runs; the proven **cross-platform** path.
   - **Antigravity** (`agy`) — Google's agentic CLI; flat-rate with a Google AI subscription.
   - **cursor-agent** — Cursor's CLI; flat-rate with a Cursor subscription.
4. *Optional:* `ANTHROPIC_API_KEY` for behavioral (G-Eval) judging; an OTLP endpoint or
   `LANGFUSE_*` keys for dashboard traces. Everything degrades to a no-op when absent.

## Platform support

- **Windows: validated.** All three providers have run real multi-slice builds headless
  (including the Windows-specific fixes that made that true: shim-bypass, stdin detachment,
  console-encoding safety).
- **macOS / Linux: engine, generator, and test suite are portable** (plain Python; CI runs
  both OSes). The **opencode** provider has a clean POSIX dispatch path and is the
  recommended non-Windows executor. **antigravity and cursor on POSIX are experimental** —
  their dispatch handling was engineered against Windows CLI behavior and hasn't been
  live-validated elsewhere. Reports welcome.

---

## Install

### Easiest: as a Claude Code plugin (two commands)

This repo doubles as a plugin marketplace. In Claude Code, add it once:

```
/plugin marketplace add jhesham/cross-llm-delivery
```

then install **the provider(s) whose CLI you have** — there are three, pick any:

```
/plugin install cross-llm-opencode@cross-llm-delivery       # free/cheap models, works everywhere
/plugin install cross-llm-antigravity@cross-llm-delivery    # flat-rate, needs a Google AI sub
/plugin install cross-llm-cursor@cross-llm-delivery         # Composer, needs a Cursor sub
```

(First time? Install just **cross-llm-opencode** — it has free models and is the proven
cross-platform path.) You still need that provider's CLI installed + logged in — see
[Prerequisites](#prerequisites). Updates flow with `/plugin marketplace update`; every push to
this repo is a new installable version.

### From source (for development, or to generate skills yourself)

```bash
git clone https://github.com/jhesham/cross-llm-delivery
cd cross-llm-delivery
python -m pip install -e ".[dev]"   # engine + test deps (otel extras included in dev)
python -m pytest                     # should pass; no API keys or executor CLIs needed
```

## Generate + install a provider skill (source route)

The monorepo ships a **generator** that produces self-contained, per-provider Claude Code
skills — `cross-llm-antigravity`, `cross-llm-opencode`, `cross-llm-cursor`. Each generated
skill needs **no pip install** (the engine is vendored into `scripts/cld/`).

```bash
python generator/build_skill.py --all        # or: build_skill.py opencode
```

(Windows convenience wrapper for a clean rebuild: `pwsh ./rebuild-skills.ps1`.)

Then copy the one you want into your Claude Code skills directory:

```bash
# macOS / Linux
cp -r dist/cross-llm-opencode ~/.claude/skills/cross-llm-opencode

# Windows (PowerShell)
Copy-Item -Recurse dist\cross-llm-opencode "$env:USERPROFILE\.claude\skills\cross-llm-opencode"
```

`dist/` is gitignored build output — always regenerate; never rely on a stale copy. Full
fresh-machine steps: [INSTALL.md](INSTALL.md).

---

## Using it — "it's installed, now what?"

`cld` is a **skill**, not a slash command that runs a build. You don't type a magic command —
you **talk to Claude Code** and it drives the pipeline. The skill is knowledge Claude loads so
it knows *how* to plan, dispatch, and judge.

The whole flow is one conversation:

1. **Plan** — describe what you want; let Claude (the architect) design it as vertical slices
   with committed acceptance tests. For example:
   > *"I want to build a CSV-import module with validation and tests. Help me plan it as slices
   > with acceptance tests I can commit."*

2. **Delegate** — once the plan and its (failing) tests are committed, hand the build to the
   skill by naming it:
   > *"Now use **cross-llm-opencode** to run this plan."*
   > *(or `cross-llm-antigravity` / `cross-llm-cursor` — whichever you installed.)*

   Claude loads that skill and drives the build: each slice runs on the cheap executor in an
   isolated worktree, the real tests decide pass/fail, failures retry and escalate — and Claude
   reports the gate after each layer so you can steer.

3. **Watch (optional)** — for a long build, ask Claude to run it in the background and poll
   `--status`, or run it yourself:
   ```bash
   python skill/scripts/run_delivery.py --status --repo .
   ```

That's it: **plan with Claude → say "use cross-llm-\<provider\> to run it" → Claude delivers and
judges.** Everything below is the detail behind those three steps.

---

## Quickstart

1. **Write a plan.** One markdown block per slice (worked example:
   [skill/examples/demo-plan.md](skill/examples/demo-plan.md)):

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

   **Author the acceptance tests first (committed, failing).** They are the objective contract
   the executor is judged against. See
   [skill/references/authoring-plans.md](skill/references/authoring-plans.md).

2. **Preview the schedule** (no dispatch): `python skill/scripts/run_delivery.py plan.md --dry-run`

3. **Run one DAG layer at a time (recommended):**

   ```bash
   python skill/scripts/run_delivery.py plan.md --repo . --step --workers 4
   ```

   Exit codes gate the loop: **0** layer passed (merge the accepted `slice-<id>` branches, then
   re-invoke), **2** some slices failed, **3** build complete, **4** a slice needs orchestrator
   repair. The ledger is the state — re-running resumes automatically.

   > **Merge before the next layer:** accepted work lands on `slice-<id>` branches; worktrees
   > branch from HEAD, so merge accepted slices into your base before running a dependent
   > layer. `--step` warns loudly if you forget.

4. **Watch it live:**

   ```bash
   python skill/scripts/run_delivery.py --status --repo .   # one-shot digest (agents poll this)
   python skill/scripts/run_delivery.py --watch --repo .    # repainting terminal view
   ```

**Choosing the executor/model.** Omit `--executor` on a TTY for the interactive picker, or pass
it explicitly: `--executor opencode:<provider/model>`, `--executor antigravity:<model>`,
`--executor cursor:<model>` (optional `@effort` suffix). An explicit model is honored verbatim;
a per-slice `executor:` tag overrides the build default for that slice. Metered models get a
cost confirmation; uncatalogued ones get a validate-before-trust probe. `--usage` prints a
combined cost/usage table.

The commands above are what the skill runs under the hood — when you [use it as a
skill](#using-it--its-installed-now-what), Claude issues them for you and interprets the gate
codes. Run them by hand for a source checkout or to drive a build yourself.

---

## Configuration

| Knob | Where | Default |
|---|---|---|
| Executor / model | `--executor <name>[:<model>][@effort]`; interactive picker if omitted on a TTY | provider default workhorse |
| Per-slice executor | `executor:` tag on a `## SLICE:`/`## SUBSLICE:` block | inherits build default |
| Workflow | `--step` (one DAG layer at a time) vs. whole-plan | — |
| Parallelism | `--workers` | 4 |
| Ledger path | `--ledger` | `.cld-ledger.json` |
| Telemetry stream | always on → `<repo>/.cld/events.jsonl` | local JSONL |
| Dashboards | `OTEL_EXPORTER_OTLP_ENDPOINT` or `LANGFUSE_PUBLIC_KEY`+`LANGFUSE_SECRET_KEY` | off |
| Status / watch | `--status`, `--watch [--interval N]` | — |
| Usage report | `--usage` | — |
| Judge model (behavioral) | `cld.behavioral.make_compliance_metric(judge_model=...)` | `claude-sonnet-4-6` |

---

## Project layout

```
engine/cld/             the engine (orchestrator, judge, ledger, dag, telemetry, status, ...)
engine/cld_providers/   one package per executor backend (antigravity, opencode, cursor)
generator/              builds self-contained per-provider skills into dist/
skill/                  skill template, scripts (run_delivery.py), references, examples
tests/                  the test suite (default run needs no API keys or CLIs)
```

The provider registry takes further drop-in adapters — one `cld_providers/<name>/` package
each (catalog + executor + skill fragment). For the module-by-module map, see
[skill/references/architecture.md](skill/references/architecture.md).

## Publishing your own mirrors (optional)

`generator/publish.py` can push each generated skill to its own mirror repo and tag it.
Configure targets in `publish-targets.toml` (gitignored; copy from
`generator/publish-targets.example.toml`), preview with `python generator/publish.py`,
push with `--execute`.

## Known issues

See [KNOWN-ISSUES.md](KNOWN-ISSUES.md) for current limitations (per-provider cost reporting
scope, cursor upstream long-prompt defect, telemetry stream lifecycle).

## License

MIT — see [LICENSE](LICENSE).
