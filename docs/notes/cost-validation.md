# T1.4 — Cost-Validation Verdict [PREMISE GATE]

**Date:** 2026-06-08
**Slice:** T2.1 Executor interface (`src/cld/executors/base.py`) — real, kept `cld` code.
**Executor:** Gemini 3.1 Pro (`gemini-3.1-pro-preview`), locked CLI form, `--yolo --skip-trust -o json`.
**Dispatch mode:** `yolo --skip-trust` (the form with a confirmed successful run on this machine).

## What was tested

The premise gate asks: **on a real, representative slice, does routing implementation to Gemini
actually cost less than doing it in Claude/Opus — enough to justify the orchestration?**

Claude authored the contract as 7 failing acceptance tests (Protocol + two dataclasses), then
dispatched to Gemini in an isolated worktree. Claude judged the result independently.

## Quality result: ✅ PASS (grade A)

- **7/7 acceptance tests pass** (run independently by Claude, not self-reported).
- Diff review against design rules: `field(default_factory=...)` for all mutable defaults,
  `@runtime_checkable` Protocol, exact `run(task, workdir) -> ExecutorResult` signature,
  stdlib-only, no I/O. Contract names match T2.2–T5 references.
- Only `src/cld/executors/` touched; tests untouched. First-dispatch correct. **Grade A.**

Quality is settled: Gemini produces clean, contract-correct `cld` code from a Claude spec.

## Cost result: ⚠️ INCONCLUSIVE on this slice — overhead still dominated

**Measured Gemini tokens (from `-o json` stats.models):**

| metric | value |
|---|---|
| total | **52,188** |
| prompt | 50,727 |
| input | 44,987 |
| **output (candidates)** | **578** |
| cached | 5,740 |
| thoughts | 883 |
| API requests | 5 (0 errors) |
| lines produced | 24 |

**The problem:** like Phase 0 (45,162 tokens / 8 lines), this run is **fixed-overhead-dominated**.
578 output tokens of actual work sit under ~50k of prompt overhead (workspace scan + system
prompt + reading the test file). The interface slice, though "real," is *small in output* — a
Protocol + two dataclasses is ~24 lines. So this slice **also does not cleanly amortize the
per-dispatch overhead**, and a per-slice dollar figure here would be measuring Gemini's fixed
cost-of-doing-business, not the cost of bulk implementation.

### Dollar framing (with explicit caveat)

Comparing on dollars (the real question — Opus and Gemini price per token differently):

- **Opus 4.8 pricing (confirmed via claude-api skill):** $5 / 1M input, $25 / 1M output.
- **Claude-equivalent estimate for *this* slice:** authoring the spec + judging already happened
  in Claude and is *intrinsic to the design* (Claude is always the architect+judge). The marginal
  question is the *implementation* tokens. Implementing this 24-line module directly in Claude
  would be on the order of ~2–4k input + ~1–1.5k output ≈ **$0.04–0.06**. Gemini's 52k tokens are
  cheap per-token, but the **comparison is dominated by Gemini's ~50k fixed overhead per dispatch**,
  not the 578 tokens of real output.
- **Gemini per-token price:** not fabricated here — Gemini 3.1 Pro Preview's published rate is not
  available in this environment. **Action: confirm the live Gemini 3.1 Pro price before relying on
  any dollar figure.** What the token *structure* already tells us does not depend on the exact rate
  (see below).

## What the data actually proves (rate-independent)

1. **The per-dispatch overhead is ~roughly fixed at ~45–50k tokens** across both Phase 0 (8 lines)
   and T1.4 (24 lines). Output scaled 8→578 tokens; overhead barely moved.
2. **Therefore the economics are entirely a function of OUTPUT SIZE per dispatch.** Small slices
   (toy or thin-interface) are overhead-bound and a poor deal. The advantage only materializes when
   a slice's implementation output is large enough that the cheap-per-token executor work dwarfs the
   fixed overhead — i.e. **bulk implementation**, exactly the design's stated target ("for large
   builds only; small fixes stay with Claude").
3. **This is consistent with the design, not a contradiction of it** — but it means the gate is
   **not yet satisfied by direct measurement.** Two thin slices in a row were overhead-bound.

## DECISION: ⚠️ CONDITIONAL GO

**Proceed to Phase 2 (build the executor adapter), with a hard follow-up gate.**

Rationale:
- **Quality is proven** (two clean A-grade dispatches). The executor *works*.
- **The mechanism is proven** (worktree → dispatch → independent judge → merge).
- **Cost is structurally understood:** overhead is fixed; advantage requires large-output slices.
  We have not *yet* measured a large-output slice, so the 10× claim remains **unvalidated by
  measurement** — but nothing observed contradicts it, and the failure mode (small slices) is
  exactly what the design already excludes.

**This is a CONDITIONAL GO, not an unconditional one.** The build continues because Phase 2's
adapter is needed regardless (it's the seam that lets us run a *large* slice through the same path),
but the premise is not closed.

### MANDATORY follow-up gate (carry forward)

Before committing to Phases 3–6 at scale, run **one genuinely large-output slice** (a 150–250 line
multi-file implementation — e.g. the T3.3 Judge module or T3.4 single-slice loop) through the
executor and re-measure. Compute real dollars with the **confirmed** Gemini 3.1 Pro rate. If a
large-output slice does NOT show a clear $ advantage over the Claude-direct estimate, **stop and
reassess the executor/model** (try `gemini-3-pro-preview`, or revisit Composer) before building the
parallel fan-out. Record that measurement here.

### Open action items
- [ ] Confirm live Gemini 3.1 Pro Preview token price (input/output/cached).
- [ ] Re-run cost measurement on a large-output slice (T3.3 or T3.4) and record $ here.
- [ ] If no advantage on a large slice → executor/model reassessment before Phase 5.

## Slice disposition

Per the user's decision to **keep** the slice (not throw it away), `src/cld/executors/base.py`
(+ `__init__.py`) is merged to master. **T2.1 is therefore complete** — built by Gemini, judged by
Claude. Even on the cost caveat, the code is correct `cld` code and is kept regardless of the gate.

---

# UPDATE — 2026-06-09: Large-slice + bulk-slice measurements + premise re-anchoring

## Correction to the premise (important)

The "**≈Opus quality at ~10× fewer tokens**" figure was **Cursor's claim for Composer 2.5** —
it was **never a Gemini 3.1 Pro claim**. Earlier framing in this doc that treated "10× fewer
tokens" as the bar for Gemini was holding Gemini to a number it never promised — a
measurement-design error. The correct question for our **chosen** v1 executor (Gemini 3.1 Pro)
is simply: **does routing a slice to Gemini cost fewer DOLLARS than implementing it directly in
Opus**, given Gemini's (cheap, heavily-cached) input pricing? That is a $ question, not a
token-ratio question.

## Two more slices measured (the carry-forward gate)

| Slice | Total tokens | Output (cand.) | Lines | Output/Total | Quality |
|---|---|---|---|---|---|
| Phase 0 (toy) | 45,162 | 498 | 8 | 1.1% | A |
| T1.4 (interface) | 52,188 | 578 | 24 | 1.1% | A |
| **T3.3 (judge)** | 78,494 | 1,063 | 51 | 1.4% | A |
| **Bulk (3 files, T3.1+T3.2+T3.4)** | 157,956 | 2,241 | 114 | 1.4% | A |

Bulk-slice token breakdown: input 73,891 fresh + **74,515 cached** + 2,241 output; 9 API
requests; 0 errors.

## What is now PROVEN (token structure)

1. **Quality: settled.** Four A-grade dispatches, four contract-correct results, zero rework.
   Gemini reliably turns a Claude-authored failing-test contract into clean, idiomatic,
   DI-honoring code. This is no longer in question.
2. **Per-dispatch token cost is ~98% input overhead, and it does NOT amortize — it scales.**
   Tripling the work (51→114 lines) left output at ~1.4% of total and pushed *total* tokens
   45k→158k, because the workspace + test re-read recurs on each internal iteration/retry.
   **Bigger slices cost proportionally more tokens, not less.** This kills any expectation of a
   *token-count* advantage from large slices on this codebase.
3. **BUT ~half the bulk prompt was CACHED (74.5k of 148k).** Gemini's input is cheap and its
   cache is cheaper still — so the *dollar* verdict can diverge sharply from the token verdict.

## DECISION: continue building; cost verdict remains OPEN pending the real $ rate

- **NOT a NO-GO.** The earlier instinct to call NO-GO was anchored to the wrong (Composer)
  benchmark. Against the correct question — Gemini $ vs Opus $ — we have **not yet computed
  dollars**, because the Gemini 3.1 Pro Preview price is not available in this environment and
  the CLI exposes no cost/usage field (confirmed: `gemini --help` has no billing surface; the
  `-o json` stats carry tokens only).
- **Industry context (user):** Gemini 3.1 Pro is noted for lower token usage / higher cost
  efficiency; cheap cached input could make the $ comparison favorable *despite* the 1.4% output
  ratio. Plausible but **unmeasured** — must be confirmed with the actual rate.

## Design input carried forward (regardless of $ outcome)

- **Prefer fewer, larger dispatches** only if $-justified — but note retries multiply the
  re-read cost, so **minimize retries** (tighten contracts so first-dispatch-correct stays the
  norm; it has been 4/4 so far).
- **Lean on Gemini's prompt caching** — keep the workspace/test prefix byte-stable across the
  dispatch + any retry so cached-input pricing applies.
- The Gemini CLI has a native `--worktree` flag — may simplify T3.2's real-git wiring later.

## Open action items (the $ close-out)
- [ ] Obtain Gemini 3.1 Pro Preview pricing (input / cached-input / output per 1M). User to
      provide what the Gemini CLI / Google billing exposes.
- [ ] Compute per-slice $ for all four slices (esp. bulk: 73,891 fresh-in + 74,515 cached-in +
      2,241 out) vs the Opus-direct estimate (Opus 4.8 = $5/1M in, $25/1M out). Record here.
- [ ] If Gemini $ < Opus $ on real slices → premise CONFIRMED, proceed at scale. If not →
      revisit executor/model (`gemini-3-pro-preview`) or batch multiple slices per dispatch.

## Slices banked from the gate
- T2.1 executor interface (merged earlier).
- **T3.3 judge module** — merged (`feat(T3.3)`), 13/13 tests, grade A.
- **T3.1 + T3.2 + T3.4** (plan loader, worktree CM, deliver_slice loop) — merged via the bulk
  slice, 11/11 tests, grade A. **Phase 3 is now effectively complete**, built by Gemini.
