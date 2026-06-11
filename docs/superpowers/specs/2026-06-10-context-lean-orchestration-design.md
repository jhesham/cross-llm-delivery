# Context-Lean Interactive Orchestration — Design

**Date:** 2026-06-10
**Status:** Design approved (brainstorming), pending writing-plans
**Author:** Claude (Opus 4.8) + jhesham@hotmail.com

## Problem & Goal

The lead (orchestrating) agent must stay **interactive** through a build — the user
steers and approves at each phase; that interaction *is* the product (it's what makes
cross-llm-delivery a *delivery system*, not a dispatcher). But when the lead agent drives
the per-slice loop turn-by-turn, every dispatch's raw output (`-o json` blobs, diffs,
pytest logs) accumulates in its conversation. Over a ~30-minute build, each turn re-reads
a monotonically growing context at input-token rates → a large Claude-token drain
(observed: a 30-minute build burned an entire session, correlating with executor activity
because that's when the lead does the most turns).

**Constraint (non-negotiable):** "run it headlessly without an agent" is NOT a valid fix —
interaction with the lead agent through each phase is an absolute requirement.

**Goal:** keep the lead agent fully interactive (steer & approve per phase) while its
context stays **flat per build**, not growing with dispatch/tool-call volume.

This was diagnosed after disproving three plausible causes (the cld behavioral G-Eval judge
= dead code at runtime; context-mode's PreToolUse hook = local JS routing, no Claude call;
giant JSON blobs = captured JSON is ~900 tokens). The real cause is inherent to interactive
orchestration of a long build, and the fix is architectural, not a config toggle.

## Core idea: batch-step orchestration

The lead agent **never runs the tight inner loop.** It drives the build **one DAG layer per
invocation**. Between layers the build process *exits* — that exit IS the pause. State lives
in the **ledger on disk**, not the agent's context.

```
┌─ Lead agent (interactive, context-lean) ──────────────────┐
│  • author plan (Step 1)                                    │
│  • loop: run ONE LAYER → read compact summary → show user  │
│          → user steers/approves → run NEXT LAYER           │
│  • answer questions from the ledger + last summary,        │
│    NOT by re-running or re-reading raw output              │
└──────────────┬───────────────────────────▲────────────────┘
               │ invoke (one layer)         │ ~10-line summary
               ▼                            │
┌─ run_delivery.py --step ──────────────────────────────────┐
│  Layer N: fan out ALL independent slices CONCURRENTLY      │
│    ┌─ Gemini agent A (worktree slice-A) ─┐                 │
│    ├─ Gemini agent B (worktree slice-B) ─┤  ← parallel,    │
│    └─ Gemini agent C (worktree slice-C) ─┘    isolated     │
│  judge each · collect to branch · update ledger            │
│  raw output → .cld/ on disk · print compact summary · EXIT │
└────────────────────────────────────────────────────────────┘
```

**Two independent knobs:** the *lead* pauses **per layer** (human pace, context-lean); the
*executors* run **N-wide in parallel within a layer** (machine concurrency). The `--step`
mode controls when the lead pauses; it does NOT serialize executors inside a layer. Existing
parallel fan-out + worktree isolation (T5.2, T5.4 — Windows-safe after BUG 1) is fully
preserved.

**Signal vs noise:**
- **In agent context (signal):** per-slice one-liners, the gate prompt, the next-batch preview.
- **On disk (noise, fetched only on explicit request):** full diffs, `-o json` blobs, pytest logs.

## Components

Only **two** new pieces; everything else is reused (`run_plan_parallel`, the ledger, the
judge, the executor).

### Component A — `--step` mode on `run_delivery.py`
**Job:** run exactly one DAG layer (the next layer with pending slices per the ledger), then exit.
- **Input:** plan path, `--repo`, `--step`, plus existing flags (`--executor`, `--workers`).
- **Behavior:** read ledger → find first layer with pending slices → run ONLY that layer (full
  concurrent fan-out within it) → judge → collect to branches → update ledger → write raw
  artifacts to `.cld/` → print compact summary → exit with a status code.
- **Exit codes:** `0` = layer done, all passed; `2` = layer done, some failed/need attention;
  `3` = nothing left (build complete); (`1` reserved for usage/IO errors).
- **Stateless between calls:** the ledger is the only memory. Re-invoking advances to the next
  layer. This statelessness IS the pause + the resumability.
- **"Next layer" definition (no ambiguity):** the next layer is the EARLIEST DAG layer that still
  has at least one slice not in `done` status. A layer with a mix of `done` + `failed` slices is
  NOT advanced past — `--step` re-runs only its non-`done` slices (failed/pending), because
  downstream layers depend on the whole layer being green. This is what makes "retry T3 then
  continue" work: fixing T3 and re-invoking `--step` re-runs just T3, and only once the layer is
  fully `done` does the next `--step` move to the following layer.

### Component B — compact summary emitter
**Job:** render a layer's `PlanResult` into ~10 lines for the agent, while raw output goes to disk.
- **To stdout (enters agent context):**
  ```
  LAYER 1 of 4  —  done
    T1  ✓ pass   2 files (+38)   attempt 1
    T2  ✓ pass   1 file  (+12)   attempt 1
    T3  ✗ FAIL   tests/test_x.py::test_z   attempt 2/2
  GATE: 2 passed, 1 failed. Inspect T3? (raw diff/log on disk)
  NEXT: layer 2 → [T4, T5]  (blocked until T3 resolved)
  ```
- **To disk (`.cld/<slice-id>/`):** full `-o json` blob, unified diff, pytest log. Read only on
  explicit user request ("show me T3's diff").
- **Contract:** A produces structured results → B renders compact stdout + writes disk artifacts.
  The agent reads only B's stdout. It CANNOT accidentally pull raw output into context — it
  isn't on stdout; inspecting requires a deliberate `Read .cld/T3/diff` on request.

## Orchestration loop & approval gates

The lead agent's fixed, lean loop:

```
1. (once) author plan → cld format → commit failing tests
2. repeat until complete:
   a. invoke: run_delivery.py <plan> --repo . --step
   b. read compact summary (~10 lines) → relay to user
   c. branch on the gate:
      • all passed     → "Layer N done, all green. Continue?"
      • some failed    → "T3 failed on <test>. Inspect / retry / edit plan / skip?"
      • complete       → "All slices done. Final ledger summary + integration gate?"
   d. user steers (free interaction — ask, inspect, redirect)
   e. act on decision → loop to (a)
```

**Three approval gates:**
| Gate | When | User options |
|---|---|---|
| Layer gate | after each layer | continue · pause · inspect a slice · adjust plan |
| Failure gate | slice failed after retries | inspect · retry-with-guidance · edit contract · skip · abort |
| Completion gate | no slices left | review summary · run integration gate · merge branches |

**Cheap, unbounded interaction:** between invocations the user can talk to the agent freely;
it answers from the ledger + the last compact summary already in context — not by re-running.
Long deliberation at a gate costs almost nothing because no raw build output accumulates.

**Escape hatch (optional, rare, NOT default):** if a single slice is unusually verbose and even
its summary would bloat context, the agent may spawn a throwaway subagent to absorb that one
slice's detail and report a one-liner. Available, not built into the core loop.

## Prompt caching (complementary lever)

Batch-step and prompt caching attack the same cost from two angles and **compound**:
- **Batch-step** reduces *how much* context accumulates (raw output stays on disk).
- **Prompt caching** makes re-reading the *stable prefix* cheap (~0.1× on cache hits), so even
  the context that does accumulate (per-layer summaries + the user's conversation) is mostly
  served from cache.

Because the loop **appends** a compact summary per layer and never edits prior turns, the prior
conversation prefix stays byte-stable — so each gate-turn can hit the cache for the entire prior
build and pay full price only for the new ~10 lines. This makes the real per-build cost even
lower than "flat ~10 lines/layer" implies.

**Cache-aware orchestration rules (these live in the SKILL.md loop — caching is harness-automatic
in Claude Code; `cld`'s Python does not control breakpoints):**
1. **Append-only, prefix-stable summaries.** Add each layer's summary at the END; never rewrite a
   prior summary. Editing earlier context invalidates the cached prefix after the edit point.
2. **Keep volatile fields out of cacheable positions.** Timestamps, per-run UUIDs, and changing
   token-count totals must not be interpolated into a stable/early position of the summary block
   (they'd churn the prefix). If shown at all, put them at the very end of the appended block.
3. **Treat `.cld/` inspection as a one-time, end-of-context injection.** When the user asks to see
   a diff/log, read it once and let it sit at the tail; do NOT re-read artifacts on later turns
   (re-injection churns the prefix). One deliberate read, not passive re-accumulation.

**Caveat:** since caching is automatic in the harness, these are *behavioral* guidance for the
agent's orchestration loop, not code in the emitter. The emitter's only caching-relevant duty is
to make the summary deterministic and stable for identical results (no incidental volatility).

## Error handling

| Failure | Behavior |
|---|---|
| Slice fails after retries | Ledger marks `failed`; the layer completes for its other slices; failure gate surfaces it. No silent halt or barrel-past. |
| `--step` crashes mid-layer | Ledger is written per-slice (atomic, B1.5) → completed slices safe. Re-invoke resumes; done slices skip, in-flight re-run. No corruption. |
| Downstream dep blocked | DAG layering already won't dispatch a slice whose deps aren't `done`. Blocked layer → summary "blocked by T3" → user decides. |
| Quota exhaustion mid-layer | Existing `quota_check` defers slices (`PlanResult.deferred`); summary reports them; resume after reset. |
| User aborts at a gate | Stop invoking `--step`. Ledger holds state; resume later with a fresh `--step`. Nothing to clean up. |

Throughline: every failure degrades to "ledger holds truth, re-invoke to resume, gate surfaces
the decision" — no special recovery code, because the ledger + per-batch statelessness make it
inherent.

## Testing

- **`--step` mode** (unit, fake executor): one invocation runs exactly one layer and exits; a
  second advances to the next; completion exits with the "nothing left" code (`3`).
- **Summary emitter** (unit): given a `PlanResult`, stdout is the compact form (no raw
  diffs/JSON) and raw artifacts are written under `.cld/`.
- **Gate classification** (unit): all-pass / some-fail / complete → correct exit codes.
- **Integration** (real git, B1.1 harness): a 2-layer plan stepped twice → correct slices in
  correct branches, ledger advances, no raw output on stdout.
- **Anti-regression (the guard that matters):** assert summary stdout is under a line/token
  budget — so the drain cannot silently creep back.

## Boundaries (YAGNI)

- **NOT a daemon / not long-running** — per-batch invocation, deliberately (avoids IPC, polling,
  hung-process handling).
- **NOT auto-merge** — collecting to `slice-<id>` branches is the contract; merge stays a
  human/agent decision at the completion gate.
- **NOT intra-slice multi-agent** — 1 slice = 1 dispatch (confirmed). Design stays compatible but
  doesn't build it.
- **NOT changing the executor or judge** — purely the orchestration/observation layer; the
  B1.3/B1.4/B1.5 fixes stand untouched.

## What this fixes vs today

Today the agent ran the whole loop in one unbroken, growing context → 30-min token bonfire.
Under batch-step, the agent's context grows by ~10 lines **per layer** (not per tool-call, not
per dispatch) and stays flat during interaction. A 4-layer build = ~4 summaries + the user's
conversation. The drain is eliminated while full steer-and-approve interactivity is preserved.
