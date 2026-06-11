# Build Status — cross-llm-delivery

> **Resume protocol (read this first every new sitting):**
> 1. Read this file — the "Next task" line tells you exactly where to start.
> 2. Read `docs/superpowers/plans/2026-06-08-cross-llm-delivery-master-plan.md` for the task detail.
> 3. Check the memory `cross-llm-delivery-project` for high-level context.
> 4. Do ONE task (or as many as the token budget allows), each ending in a commit + an update to this file.
> 5. Before stopping, update "Last updated", tick the task in the master plan, and set "Next task".

**Last updated:** 2026-06-09 (✅ COST GATE CLOSED = GO; Phases 2–3 built early by Gemini)

**Next task:** Resume advisor build (Sitting B) — but READ THE TOKEN-DRAIN FINDING FIRST (below).

🔍 **CLAUDE TOKEN-DRAIN INVESTIGATION — RESOLVED 2026-06-10.** User: "30 min burned the whole Claude session, observed ONLY while Gemini actively developing, lead Claude appeared inactive." **THREE compelling theories DISPROVEN by reading the actual code (validation > certainty, again):**
- ❌ **cld behavioral G-Eval judge** — `evaluate_compliance`/`make_compliance_metric` are referenced ONLY in behavioral.py + the gated `-m eval` test + docs. NOTHING in the live path (orchestrator/judge/run_delivery) imports or calls them. Dead code at runtime. Verified by grep.
- ❌ **context-mode PreToolUse → Claude subagent** — its hook (`hooks/core/routing.mjs::routePreToolUse`) returns LOCAL decision objects (`{action:"redirect"|"context", ...}` or null); it does NOT call the Anthropic API or spawn a Task/Claude subagent. The "subagent routing" = redirect-to-MCP-tool or inject-a-text-string (~85–500 tok, periodic). Not a per-call Claude bill.
- ❌ **Giant `-o json` blobs flooding lead context** — captured dispatch JSON is ~900 tokens; `run_delivery.py` prints only completed/failed/skipped/deferred summaries. No raw-blob leak.
- ✅ **ACTUAL CAUSE: interactive orchestration.** When the LEAD agent (Claude) babysits a Gemini build turn-by-turn, each turn re-reads the ENTIRE growing conversation (every prior dispatch/diff/test-log/analysis) at input-token rates. Over 30 min = dozens of turns × a monotonically growing context = large spend. Correlates with "Gemini developing" because that's when the lead does the most turns; "lead inactive" is misleading — it's not THINKING hard, but every turn still CARRIES the fat accumulated context.
**THE FIX (mostly usage, not code): run builds HEADLESSLY, detached from the lead agent.** `python skill/scripts/run_delivery.py <plan> --repo <dir>` run by the USER in a terminal = the whole build (dispatches, diffs, tests) happens in THAT process = ~0 lead-Claude tokens. Bring back only the ledger/summary for Claude review. The lead agent's job is author-the-plan (Step 1) + review-the-outcome, NOT babysit each dispatch. **Optional code hardening (low priority):** ensure no large executor output (raw_log) is ever surfaced to an interactive caller; consider a `--summary-only` quiet mode. Pre-emptively gate `cld.behavioral` behind an explicit opt-in flag so it can never accidentally bill Claude if wired later.

**After this:** ✅ BUG 1 + BUG 2 fixed; resume advisor build (Sitting B, S4–S5) — **run it headlessly per the finding above.** Advisor plan: `rac-agent/docs/superpowers/plans/2026-06-08-advisor-langgraph-plan.md` (transcribe to cld `## SLICE:` format = Claude Step 1). 123 passed. Then OpenCode CLI 2nd executor (roadmap step 2).

🔧 **FIRST-LIVE-RUN BUGS context (rac-agent advisor S1–S3, 2026-06-09):**

### BUG 1 — "worktree collision" → ACTUALLY a capture/judge-path architectural gap (HIGH)
**DIAGNOSED 2026-06-09 (systematic-debugging). The git-worktree-race theory was DISPROVEN by reproduction:** concurrent `git worktree add` runs 3/3 clean every time on this Windows host (see `docs/notes/bug1_repro.py`). Isolation works. The real root cause is THREE coupled defects in the capture-and-judge path (all masked by our fake-runner tests — only a REAL run exposes them):
1. **`git diff HEAD` can't see new files.** `GeminiExecutor` captures `files_changed` via `git diff HEAD --name-only`, but NEW slice files are UNTRACKED — `git diff HEAD` omits untracked files without a prior `git add`. So `files_changed` is EMPTY for any slice that creates files → "S1 done with no code."
2. **The judge never re-runs tests.** `run_delivery.py::make_judge_fn` passes `run_tests=lambda: result.raw_log` (the executor's OWN stdout), NOT a fresh pytest run in the worktree — despite the comment claiming it does. The ledger labels are derived from UNVERIFIED executor self-report.
3. **No defined "collect result from worktree" step.** The pipeline never `git add`s / commits / merges the worktree back; it implicitly relies on Gemini self-committing (unmanaged) → "code landed on slice-S2."
**This is an architectural gap, not a one-line race fix — NOT pure-dogfood-able.** Needs a design decision (Claude): should the pipeline `git add -A` in the worktree before diffing? should the judge run REAL pytest in `wt_path`? should there be an explicit commit+collect step? THEN individual fixes could be dogfooded. **Mitigation still valid:** `--workers 1` + verify-then-cherry-pick (what the user did). **Add a REAL integration test** (real temp git repo, real subprocess runner, a slice that CREATES a file) — the fake-runner tests can never catch this class of bug.

#### BUG 1 DECOMPOSED into sitting-sized tasks (2026-06-09) — do in order, each ends in a commit:
- **B1.1 — Real integration-test harness ✅ DONE (84e4364).** `tests/integration/` — real subprocess `git_runner`, `init_repo` (real repo + HEAD), `FileCreatingExecutor` (writes the slice's files for real + captures via GeminiExecutor's git-diff logic). 4 smoke tests; `integration` marker registered (runs by default). **Confirmed it OBSERVES Defect 1 live:** created file exists + `git status` shows `?? src/`, but capture's `files_changed` is `[]`. 118 passed.
- **B1.2 ✅ DONE (1b4024e).** Failing test for Defect 1 — Using B1.1, assert `files_changed` currently comes back EMPTY for a created file (reproduces the bug as a RED test). Debugging discipline: pin before fix.
- **B1.3 ✅ DONE (dogfood, grade A).** git add --intent-to-add before diff — Executor `git add -A` (or `--intent-to-add`) before `git diff` so new files appear in `files_changed`; B1.2 goes green. First dogfood-able piece (real "make this failing test pass"). Fits a LOW window.
- **B1.4 ✅ DONE (a0388bc).** Judge runs REAL pytest in worktree via deliver_slice test_runner — `make_judge_fn` runs REAL pytest in the worktree (`python -m pytest <acceptance_test>` in `wt_path`), not `lambda: result.raw_log`. Test: judge fails wrong code, passes right code — verified by real execution. THE load-bearing fix (why the ledger lied); judge is the safety core, Claude writes it.
- **B1.5 ✅ DONE (1c27276).** Collect-from-worktree (commit accepted slice before removal) + concurrent regression test — Decide & implement how a slice's result is committed/collected back. Real CONCURRENT integration test: 2 slices' distinct files land in distinct branches. Largest; do last when others are solid. Save for a fuller window.
- **Suggested grouping:** B1.1+B1.2+B1.3 = one satisfying arc in a low window (harness → red → dogfood-green). B1.4 own sitting. B1.5 a fuller window.

### BUG 2 — No way to choose the executor/model at invocation ✅ FIXED 2026-06-09
`run_delivery.py` now has `--executor gemini[:<model>]` (default gemini); `parse_executor_spec`
splits name:model and passes model through to `get_executor`. 6 tests; verified end-to-end via
--dry-run. The USER picks the LLM at invocation (not the orchestrator). Forward-compatible with
the future `opencode:<provider/model>` executor.
(NB STILL OPEN if the real complaint was "Gemini edits beyond its slice contract / goes
off-script" — that's NOT model selection, it's a PROMPT/diff-rule-enforcement issue: the judge's
diff-rule already FLAGS out-of-bounds edits, but the executor prompt could be made stricter to
PREVENT them. Clarify with user which problem they meant.)

## POST-BUILD ROADMAP (gated by the user, 2026-06-09) — sequence matters

The plan is done; these are the gates to *wider sharing*. Do them IN ORDER — do not jump to publishing.

1. **LIVE TEST(S) on a real use case.** User finds a real build, runs it via the skill
   (`python skill/scripts/run_delivery.py <plan.md> --repo <dir>`), sees how it goes. First
   EXTERNAL use — will surface what our internal 11/11 clean dogfood runs never did.
   - **Claude review after each run** (user requested): point Claude at the repo + the ledger
     (`.cld-ledger.json`) + run output. Review covers: per-slice pass/fail/attempts, Gemini's
     diffs (quality + diff-rule compliance), real token/quota cost, retry/self-correction
     behavior, and whether the SLICING (not the executor) was the bottleneck. Iterate on findings.
   - Repeat until it works well "a few times" (user's bar before considering sharing).
2. **Incorporate the OpenCode CLI as a second executor** (user-confirmed 2026-06-09: OpenCode
   CLI, not OpenAI). Only after live testing proves the core. Add `OpenCodeExecutor` to the
   registry (the `composer` stub slot), wrapping `opencode run "..." --model provider/model
   --format json --dangerously-skip-permissions --dir <wt>`. See
   `docs/notes/opencode-executor-option.md` for the CLI mapping + cost caveat (Zen is metered
   pay-as-you-go — keep Gemini flat-rate as DEFAULT; OpenCode opt-in, best on its cheap/free
   tier). Mirror GeminiExecutor's shape: build argv, run via injected runner, parse tokens,
   capture diff. Validate with one dispatch through `opencode run --format json` first.

   **EXECUTOR-SELECTION DESIGN (decided 2026-06-09, ours differs from sub-agents-skills):**
   The USER chooses the LLM at invocation — NOT the orchestrating Claude autonomously. Two levels:
   (a) **Run-level** `--executor gemini|opencode:<provider/model>` flag on `run_delivery.py`
   ("run this whole build on X"); default `gemini` (flat-rate, $0 marginal).
   (b) **Per-slice override** (optional) via an `executor:` field in the plan markdown, for
   "send this one heavy slice to a stronger model"; inherits run-level if absent.
   **DELIBERATELY AVOID** orchestrator-autonomous per-dispatch model picking — it breaks
   reproducibility, hides cost, and makes the paid backend unpredictable. User-explicit beats
   agent-clever (same principle as the T6.3 hook defaulting hands-off).
   Prior art: sub-agents-skills (github.com/shinpr/sub-agents-skills) uses author-locked
   `run-agent:` frontmatter + a `--cli` override + default; their UNIT is the agent/task, OURS
   is the plan/build — hence run-level default + optional per-slice override fits us better.
   Their backend-selection priority chain (explicit flag → frontmatter → auto-detect → default)
   is a clean pattern worth mirroring in the registry.
3. **THEN consider wider sharing** — possibly publish to GitHub. Not before steps 1–2 pass.

**Gate rationale:** prove on real work → multi-executor → publish. Don't share an untested tool.

> ✅ **COST GATE CLOSED = GO.** Decisive fact: Gemini runs on a **flat-rate plan** (Google AI Pro, A$32.99/mo) — billing is **quota %, not per-token** (CLI shows "Pro 24%, resets 12h"). So executor tokens are **$0 marginal**; the token-overhead finding (~98% input, non-amortizing) is economically **irrelevant** under flat billing. vs Opus-direct (~$0.42/bulk slice metered) Gemini wins decisively. Quality proven 4/4 grade A. **New constraint = quota/rate budget, not $:** make the orchestrator quota-aware (throttle/Flash-fallback near cap) for Phase 5 fan-out. See `docs/notes/cost-validation.md` → "COST GATE CLOSED".

> 🔀 **Routing policy (decided 2026-06-09): SELECTIVE dogfooding.** Use the product where it pays, not as ritual. **Dogfood (Gemini-dispatched, Claude authors contract + judges)** clean self-contained logic with a fully test-pinnable contract: **T4.1, T5.1**. **Claude writes directly** the judgment/concurrency/prose tasks: **T5.2** (parallel fan-out — needs quota-awareness), **T6.1/6.2/6.3** (skill packaging, docs, hook). **Borderline (decide at the time):** T4.2 (edits orchestrator.py), T5.3 (wires real verify/merge). Rationale: thesis proven 5/5 grade A; remaining bottleneck is contract-authoring+judging, so dispatch only when it's the cheaper path.

## Progress ledger

| Task | Phase | Status | Commit |
|------|-------|--------|--------|
| Design + plan | — | ✅ done | 1f8dd98 |
| Phase 0 (executor smoke test) | 0 | ✅ GO | d734534 |
| T1.1 Project scaffold | 1 | ✅ done | e265425 |
| T1.2 Langfuse tracing | 1 | ✅ done | 5b075bb |
| T1.3 deepeval harness | 1 | ✅ done | 7e7815a |
| T1.4 Cost-validation slice | 1 | ✅ GO (gate closed) | a99a121 |
| T2.1 Executor interface | 2 | ✅ done (via T1.4) | d8b2bf6 |
| T2.2 GeminiExecutor adapter | 2 | ✅ done | 9520e00 |
| T2.3 Executor registry + Composer stub | 2 | ✅ done (dogfood) | d95d15a |
| T3.1 Slice spec model | 3 | ✅ done (via bulk) | f94707a |
| T3.2 Worktree manager | 3 | ✅ done (via bulk) | f94707a |
| T3.3 Judge module | 3 | ✅ done | f94707a |
| T3.4 Single-slice loop | 3 | ✅ done (via bulk) | f94707a |
| T4.1 Ledger schema | 4 | ✅ done (dogfood) | 3370a7e |
| T4.2 Resumable orchestrator | 4 | ✅ done (dogfood) | 55c4ba0 |
| T5.1 DAG scheduler | 5 | ✅ done (dogfood) | 730bc92 |
| T5.2 Parallel fan-out | 5 | ✅ done (Claude) | faee112 |
| T5.3 Integration gate | 5 | ✅ done (dogfood) | ebffe51 |
| T5.4 Worktree isolation (parallel) | 5 | ✅ done (Claude) | 2d300e4 |
| T5.5 Langfuse span emission | 5 | ✅ done (Claude) | d840653 |
| T5.6 Behavioral eval (Claude judge, G-Eval) | 5 | ✅ done (mixed) | a51bf1f |
| T5.7 GeminiExecutor consumes feedback | 5 | ✅ done (dogfood) | 2350b6a |
| T6.1 Package as skill | 6 | ✅ done (Claude) | 17ffe1b |
| T6.2 Sharing docs/README | 6 | ✅ done (Claude) | b9c4fcd |
| T6.3 (opt) enforcement hook | 6 | ✅ done (Claude) | 93a66e1 |
