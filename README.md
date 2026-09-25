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
  after a layer is accepted → integration gate (explicit scoped suite on the merged tree)
```

- **Vertical slices**, each independently testable, with stable contracts so a bad slice's
  rework stays local. Split larger work into top-level `## SLICE:` blocks linked by `deps`; `SUBSLICE` blocks are rejected.
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

For builds using the current source CLI, `--status` reads the persisted usage summary and
shows model totals, active reservations and budget blocks without scanning the full event log.
Attempt artifacts retain slice attribution and retry reasons. Unknown cost stays unknown,
including subscription usage without a reported charge. For example, the summary lines may show:

```text
attempts: 3  in-flight reservations: 0
tokens: 30  cost USD: unknown (0.24 known; 1 unknown attempts)
by model:
  cursor:composer-2.5  tokens: 10  cost USD: unknown (0 known; 1 unknown attempts)
  opencode:opencode/deepseek-v4-pro  tokens: 20  cost USD: 0.24
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
- **Source-engine collection is checked.** On the T03 refactoring branch, a passing
  candidate must become a verified, reachable commit with a durable outcome and ledger
  entry before cleanup. Failed attempts retain their worktrees; failures to save evidence
  report the retained path. Committed plugin bundles will receive this change at the
  distribution refresh.
- **Recovery is recorded per attempt.** Source-engine runs save binary-capable patches,
  provider output and pytest output under `.cld/<slice>/<session>/attempt-<n>/`.
  `outcome.json` records the original base, recovery refs and any collected commit. Patches
  are checked by reconstructing their tree in an isolated index. Apply a patch only to
  a clean checkout of its recorded base. See [T03 recovery notes](docs/plans/codex-support/T03-EVIDENCE.md).
- **Preflights, not tracebacks.** Before dispatching, `cld` checks the executor CLI actually
  resolves (friendly message + installed alternatives if not) and warns loudly if a pending
  layer depends on accepted-but-unmerged slice branches (the dep-blind-worktree trap).
- **Escalation is bounded and visible.** A failing slice retries with judge feedback, then
  climbs the model ladder; every switch is a telemetry event with its reason (`source`).

## Usage and admission budgets

The source CLI records every validation, retry and escalation attempt. `--status` and `--usage`
show cumulative persisted totals; missing tokens or cost remain **unknown**, including Antigravity
usage for which no verified report is available. No subscription is assumed to cost zero.

Set `--budget-attempts N`, `--budget-tokens N` and/or `--budget-cost USD` to limit new dispatches.
Token/cost limits require positive `--attempt-tokens N` / `--attempt-cost USD` reservations chosen
for your model/account. These reserve capacity before concurrent calls; they do not stop an
already-running provider at a token or dollar boundary. Actual overruns block subsequent calls.
`--unknown-usage deny` blocks further budgeted work after an unmeasured call; explicit `reserve`
charges its recorded allowance while keeping displayed usage unknown. Omitted flags retain the
build's prior policy on resume. Validation uses the same budget as production and still needs its
separate validation spend policy. See the [usage contract](docs/plans/codex-support/T10-CONTRACT.md)
for recovery, historical-data limits and normalization semantics.

## Providers & models

Three executor providers ship today. Each carries a vendored catalog with a **cost class** and a
**validation status** — `cld` won't quietly trust an unproven model: uncatalogued or untested
models require a **validate-before-trust probe** (one trivial slice, judged for real) before a build
commits to them. The source CLI applies this to every selected model, including fallback rungs;
static catalog claims alone do not authorize dispatch. Outcomes live in
`~/.cld/validation-evidence.json`.

Validation defaults to `--validation-policy deny`: current verified evidence can be reused,
but a needed probe returns gate 5 with a recorded blocked reason. Choose `unmetered` to permit
probes for catalogued free/flat models, or `allow` to permit metered and unknown-cost probes.
These labels are catalog classifications, not a billing guarantee. No validation prompt is used.
`--revalidate-models` forces a new probe, including previously failed models, and still requires
a spend policy. Evidence expires after 30 days (`--validation-max-age` sets seconds). Changes to
model/effort, CLI files, repository, environment, or tracked config invalidate it. Use repeatable
`--validation-config PATH` and `--validation-context ID` for other configuration/account inputs.
Probe repositories, recovery artifacts, usage and admission decisions are retained under the
build run directory. Cumulative admission limits are available in the source CLI (see below). Generated plugin
copies receive these source changes in T12/T17.

| Provider | Cost model | Catalog highlights | Proven in real builds¹ |
|---|---|---|---|
| **antigravity** (`agy`) | flat-rate (Google AI sub) | Gemini 3.1 Pro (default workhorse), Gemini 3.5 Flash tiers, Claude Sonnet/Opus (Thinking), GPT-OSS 120B | Gemini 3.1 Pro (High) |
| **opencode** | free tier + cheap/premium metered | deepseek-v4 (incl. a **free** tier), kimi-k2.7-code, GLM-5.x², Gemini 3.1 Pro, Claude Sonnet/Opus | kimi-k2.7-code, deepseek-v4-pro, gemini-3.1-pro, GLM-5.2 |
| **cursor** | subscription | composer-2.5 | composer-2.5 (16-slice application build) |

¹ *"Proven" = accepted real slices in live builds during this tool's development (real pytest
gates, worktree isolation) — including the dogfood builds where these executors implemented parts
of `cld` itself. Validation statuses live in a machine-local evidence store; on your machine, the
validate-before-trust probe re-establishes them under the explicit validation policy.*
² *Uncatalogued models (e.g. `opencode/glm-5.2`) are usable via an explicit per-slice `executor:`
tag; the probe covers them too.*

**New models need no code changes.** Any model your executor CLI exposes works today — run the
CLI's own model listing (e.g. `opencode models`) and pass the exact id via
`--executor provider:model` or a per-slice `executor:` tag; the validate-before-trust probe
covers models `cld` hasn't seen. The catalog above is curated recommendations, not a gate — so
when a provider ships a new model, you don't wait for this repo to catch up.

New **provider CLIs** are drop-in: one `cld_providers/<name>/` package (catalog + executor +
skill fragment) — see [CONTRIBUTING.md](CONTRIBUTING.md).

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

1. **Python ≥ 3.11** and **git** (any modern git — worktree isolation runs `git worktree
   add/remove`, built into git since 2.5; nothing extra to install). The target you build in
   must be a git repo — run `git init` first if it isn't. `cld` checks both at startup and tells
   you if either is missing.
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

The offline CI matrix exercises Python 3.11 and 3.14 on Windows and Ubuntu. Each job
runs the full default test suite, builds all eight Claude/Codex provider bundles, checks
the tracked Claude plugins, and packages the Codex plugins/catalog. The installed-wheel
regression also runs with optional packages excluded. Python 3.13 has a separate local
Windows full-suite pass; Python 3.12 and macOS have no current CI coverage.

Historical live headless Windows builds cover the original three executors. The Codex
executor has a separately recorded Windows canary in the T16 evidence. The current CI matrix
makes **no live provider calls**, so its green status proves offline contracts, not live
provider operation on every host. OpenCode has a POSIX dispatch path, but live dispatch
on Ubuntu/macOS is not established by this matrix. Antigravity and cursor dispatch on
POSIX remain experimental. Codex plugin discovery was checked separately on Windows;
Claude and Codex host installation/rehearsal across platforms belongs to T14/T19.

---

## Install

### Easiest: as a Claude Code plugin (two commands)

This repo doubles as a plugin marketplace. In Claude Code, add it once:

```
/plugin marketplace add jhesham/cross-llm-delivery
```

then install **the provider(s) whose CLI you have** — pick any:

```
/plugin install cross-llm-opencode@cross-llm-delivery       # free/cheap models, works everywhere
/plugin install cross-llm-antigravity@cross-llm-delivery    # flat-rate, needs a Google AI sub
/plugin install cross-llm-cursor@cross-llm-delivery         # Composer, needs a Cursor sub
/plugin install cross-llm-codex@cross-llm-delivery          # exact Codex model required; cost unknown
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
skills — `cross-llm-antigravity`, `cross-llm-opencode`, `cross-llm-cursor`,
`cross-llm-codex`. Each generated
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

   Exit codes: **0** operation succeeded with work remaining, **2** failure/defer,
   **3** fully integrated build, **4** lead repair required, **5** invalid input/state,
   lock or policy block, **6** accepted work awaits integration.

   Integrate the exact accepted commits using an explicit scoped suite:
   ```bash
   python skill/scripts/run_delivery.py plan.md --repo . --integrate --integration-tests tests/test_integration.py
   ```
   Later slices use that verified integration SHA. The user's checkout is untouched;
   dependencies block until integration succeeds. See the [current CLI and plan
   contract](docs/plans/codex-support/T07-CONTRACT.md) for source-engine behavior.

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
| Per-slice executor | `executor:` tag on a `## SLICE:` block | inherits build default |
| Workflow | `--step` (one DAG layer at a time) vs. whole-plan | — |
| Parallelism | `--workers` | 4 |
| Dispatch deadline (seconds) | `CLD_DISPATCH_TIMEOUT`; executor `timeout=` overrides it | 600 |
| Model-listing/account probe deadline (seconds) | `CLD_PROBE_TIMEOUT` | 30 |
| Ledger path | `--ledger` | `.cld-ledger.json` |
| Telemetry stream | always on → `<repo>/.cld/events.jsonl` | local JSONL |
| Dashboards | `OTEL_EXPORTER_OTLP_ENDPOINT` or `LANGFUSE_PUBLIC_KEY`+`LANGFUSE_SECRET_KEY` | off |
| Status / watch | `--status`, `--watch [--interval N]` | — |
| Usage report | `--usage` | — |
| Judge model (behavioral) | `cld.behavioral.make_compliance_metric(judge_model=...)` | `claude-sonnet-4-6` |

Source executors stop their owned process trees before returning or preserving
partial edits. Ctrl-C cancels active delivery workers; cancelled dispatches do not
retry. Both output streams are retained under the attempt's `processes/` directory
and linked from `dispatch.json`; standalone probes use retained OS-temp artifacts.
Deadlines must be finite positive seconds. See the [process contract](docs/plans/codex-support/T08-CONTRACT.md)
for platform boundaries and the legacy injected-runner contract. Generated plugin
copies receive these changes in the planned packaging slices.

---

## Project layout

```
engine/cld/             the engine (orchestrator, judge, ledger, dag, telemetry, status, ...)
engine/cld_providers/   one package per executor backend (antigravity, opencode, cursor, codex)
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
