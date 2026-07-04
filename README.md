# cross-llm-delivery (`cld`)

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

## Where this fits (and what it pairs well with)

Multi-model development is a rich space, and several excellent tools solve adjacent problems.
`cld` occupies one deliberately narrow niche — **batch implementation you can hold accountable
with tests you wrote first** — and it composes happily with the rest:

- **[aider](https://aider.chat)** pioneered the architect/editor split for interactive pairing —
  the same philosophy `cld` applies to planned batch builds. Many people will want both: aider
  for hands-on sessions, `cld` when a build is big enough to decompose and delegate.
- **[claude-code-router](https://github.com/musistudio/claude-code-router)** pulls a different
  cost lever: it makes *the assistant's own turns* cheaper by routing them to other models.
  `cld` keeps Claude in the driver's seat and makes *the implementation* cheap instead — the
  two approaches are independent and can even be used together.
- **[PAL MCP](https://github.com/BeehiveInnovations/pal-mcp-server)** and the CLI-bridge MCP
  servers excel at multi-model *consultation* — second opinions, cross-model reviews, debate.
  A natural pairing: consult before you plan, then hand the agreed plan to `cld` to deliver.
- **Swarm/orchestration platforms** (e.g. [ruflo](https://github.com/ruvnet/ruflo),
  [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)) offer broad multi-agent
  workflow suites, of which executor delegation is one feature among many. `cld` is the
  opposite trade: a single-purpose delivery pipeline you can drop into any workflow.
- **[Bernstein](https://github.com/sipyourdrink-ltd/bernstein)** shares `cld`'s conviction that
  agent output should be gated on real signals rather than opinions, with its own emphasis
  (deterministic scheduling, a wide CLI-adapter catalog, audit trails). If that framing
  resonates, it's well worth a look too.

What `cld` itself brings to that table: the **acceptance tests are committed, failing, before
dispatch** — so the merge gate is a pytest exit code plus an allowed-files diff rule, with
judge feedback carried into retries and an escalation ladder when the cheap model isn't enough.

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

```bash
git clone <this-repo-url> cross-llm-delivery
cd cross-llm-delivery
python -m pip install -e ".[dev]"   # engine + test deps (otel extras included in dev)
python -m pytest                     # should pass; no API keys or executor CLIs needed
```

## Generate + install a provider skill

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

### As a Claude Code skill

Install a generated `dist/cross-llm-<provider>/` skill (above) and ask Claude Code to run a
build with it — Claude authors the plan + acceptance tests, drives `--step`, reads `--status`,
and handles gate-4 repairs. The skill's `SKILL.md` carries the full workflow.

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
each (catalog + executor + skill fragment).

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
