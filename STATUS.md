# Build Status — cross-llm-delivery

> **Resume protocol (read this first every new sitting):**
> 1. Read this file — the "Next task" line tells you exactly where to start.
> 2. Read `docs/superpowers/plans/2026-06-08-cross-llm-delivery-master-plan.md` for the task detail.
> 3. Check the memory `cross-llm-delivery-project` for high-level context.
> 4. Do ONE task (or as many as the token budget allows), each ending in a commit + an update to this file.
> 5. Before stopping, update "Last updated", tick the task in the master plan, and set "Next task".

**Last updated:** 2026-06-19 (✅✅ SPEC #1 COMPLETE — Complexity routing + slice simplification; 317 passed; final review = FEATURE-COMPLETE)

**✅✅ SPEC #1 COMPLETE — Complexity-Based Model Routing + Slice Simplification (2026-06-19, commits
5f16641→2dfb326, 317 passed).** All 3 sub-plans shipped subagent-driven (every task 2-stage reviewed);
final whole-feature review = **FEATURE-COMPLETE** (no Critical/Important; core invariant verified at
runtime: a premium/`tier=None` model can never be selected as an executor; orchestrator stays
catalog-agnostic). What the feature delivers:
- **Flat slice model** (sub-slices + old forced per-slice picker removed) + neutral trust vocab
  (`verified`/`likely`/`untested`/`revalidate`) with lossless legacy-evidence migration on load.
- **`SliceTask.complexity`** (`easy`/`standard`/`complex`) drives an **escalation ladder**:
  quick → workhorse → **orchestrator-handoff**. The expensive model is NEVER an executor — when all
  cheap rungs fail, the slice becomes `needs_repair` (gate code **4**) and the lead agent repairs the
  failing delta, then `run_delivery.py --mark-repaired <id>` + re-`--step`.
- **Trust-aware routing:** `resolve_tier_model` picks the cheapest *viable* model per provider/tier
  (skips `revalidate`; untested only as last resort; flat gemini workhorse always available).
- **Driver wired** (`build_rung_planner` at both `run_plan_parallel` call sites) so the ladder runs
  live; **`render_routing_plan`** one-screen plan; ledger records complexity/chosen_by/final_rung/
  intervened; **per-provider usage** with complexity/rung columns; SKILL.md control-flow + rubric.
- Run-modes (advise/autonomous/review/adjust) are **lead-agent chat behavior** documented in SKILL.md
  — there is **no CLI `--autonomous` flag** (the engine can't do the repair, so a flag would be a no-op).

**Residual MINORS (non-blocking, for whenever — none affect correctness):** pre-existing non-ASCII
glyphs in `summary.py` (~76-77, predate this work); `plan_rungs` getattr/`[]` defensive-style nit
(models.py); no dedicated de-dupe/missing-quick edge tests for `plan_rungs`; a few stale "proven"
comments in tests.

**NEXT: Spec #2 — the C1 per-provider skill split** (single-source engine + generator stamping
self-contained `cross-llm-<provider>` skills; per-provider usage reporters move into provider dirs;
distribution at root or per-provider level). Needs its OWN brainstorm → spec → plan. **AWAIT a fresh
go-ahead.**

**✅ SUB-PLAN 2/3 COMPLETE — Routing + escalation ladder (2026-06-19, commits 08adf80→198fcff, 307
passed).** Subagent-driven; every task 2-stage reviewed; final whole-branch review = READY-TO-MERGE.
- **Catalog `tier`** (`quick`/`workhorse`/`None`) on `ModelInfo` (distinct from capability_class —
  Composer 2.5 = heavy capability but workhorse tier; premium = None, never an executor).
- **`resolve_tier_model(provider, tier, *, evidence, available_ids)`** — cheapest *viable* model in a
  provider tier (filters on `info.provider`; skips `revalidate`; untested only when nothing better;
  gemini flat workhorse always available). Trust rules from SP1 honored end-to-end.
- **`COMPLEXITY_ROUTING` + `plan_rungs`** — easy→quick(1)→workhorse(2); standard→workhorse(2);
  complex→workhorse(1); tagged slice → single pinned rung; empty→fallback.
- **Orchestrator escalation ladder** via an INJECTED `rung_planner` (orchestrator stays
  catalog-agnostic — took no new import of models.py). Climbs quick→workhorse; all cheap rungs fail
  → `needs_repair` HANDOFF (`final_rung="orchestrator"`), NOT `failed`. `rung_planner=None` = exact
  prior behavior.
- **Ledger** records complexity/chosen_by/final_rung/intervened (back-compatible).
- **`--step` gate code 4** = a slice needs orchestrator repair; summary surfaces it; 0/2/3 unchanged.

  (All SP2 carry-forwards for SP3 are now RESOLVED: the gate-4 repair loop uses `--mark-repaired`
  to mark a repaired slice `done` before re-`--step` so it isn't re-dispatched; the real `rung_planner`
  is wired; the run-modes live in SKILL.md as chat behavior, NOT a `--autonomous` CLI flag.)

**(prior) ✅ SUB-PLAN 1/3 COMPLETE — Foundation; 288 passed**

**🚧 IN FLIGHT — Complexity-Based Model Routing + Slice Simplification (spec #1 of 2).**
Spec: `docs/superpowers/specs/2026-06-19-complexity-routing-and-slice-simplification-design.md`.
Master plan: `docs/superpowers/plans/2026-06-19-complexity-routing-MASTER.md` (3 sub-plans).
Execution: subagent-driven, ONE sub-plan per sitting, pause between (recorded preference).

**✅ SUB-PLAN 1/3 COMPLETE — Foundation (2026-06-19, commits 1e63d1d→8110245, 288 passed).**
Subagent-driven; every task 2-stage reviewed; final whole-branch review = READY-TO-MERGE.
- **Status vocab renamed** to `verified`/`likely`/`untested`/`revalidate` across catalog +
  recommend/browse + evidence + validate; **legacy evidence files auto-migrate losslessly on load**
  (`proven`→`verified`, `known-bad`→`revalidate`). No old vocab in `src/` (bar the migration map).
- **Sub-slices removed** (fields, `## SUBSLICE:` parse, orchestrator child path, usage nesting) +
  their tests + their skill docs. Leaf behaviour unchanged.
- **Old forced per-slice picker removed** (`slice_pick_fn`, `make_slice_pick_fn`, `--per-slice-pick`)
  + its tests + its skill docs; resolution is now tag > build-default.
- **`SliceTask.complexity`** added (`easy`/`standard`/`complex`, default `standard`) + parse +
  round-trip. **Data only — nothing routes on it yet** (that's sub-plan 2).
- Global skill copies synced. Carried Minors (cosmetic, for later): a few stale "proven" comments in
  tests; `_MIGRATE` could be module-level.

**NEXT: Sub-plan 2 — Routing + escalation ladder** (`2026-06-19-part2-routing-ladder.md` — to be
written in full bite-sized detail just-in-time, against the now-simplified engine). Catalog tier
tags (`quick`/`workhorse`) + trust-filtered `resolve_tier_model` + complexity→entry-rung +
the quick→workhorse→orchestrator-handoff ladder + new `needs_repair` status & gate code 4 + ledger
recording. **AWAIT a fresh go-ahead before starting** (one-sitting-per-sub-plan). Then sub-plan 3
(control surface + per-provider usage). Spec #2 (the C1 per-provider split) is after all of spec #1.

---

**(prior) ✅✅ ALL 4 PARTS SHIPPED — scalable-picker-and-cursor feature COMPLETE; 293 passed**

**✅ PART 4/4 COMPLETE — Sub-slices (one level) (2026-06-15, commits 0bc0f2c→a47ab66, 293 passed).**
Subagent-driven (+ one Gemini dogfood), all 5 tasks 2-stage reviewed + a final SHIP integration
review. Delivered:
- `src/cld/executors/base.py` — `SliceTask.parent_id` + `subslices` fields (additive, backward-compatible).
- `src/cld/plan/slice.py` — `load_slices` parses `## SUBSLICE:` under the current `## SLICE:`
  (subslices NOT top-level; parent_id set); `slices_to_markdown` round-trips them. **DOGFOOD: built by
  Gemini, Claude-judged green** (the 90%-to-Gemini-workhorse touchpoint for this part).
- `src/cld/orchestrator.py` — `_run_subslices` runs a parent's children IN ORDER, each via
  `_executor_for` (tag/default/per-slice-review per child); ledger keyed `parent/child` with
  model+effort+tokens; parent done **iff all children accepted**; a failed child fails only itself
  (its id surfaces in the parent's failure detail); worktree-per-child when repo_dir+git_runner set.
  Leaf-slice path byte-for-byte unchanged.
- `src/cld/usage.py` — `render_usage_table` nests child rows (`parent/child` keys) under their parent
  regardless of ledger insertion order; orphan children still render; build total counts all; ASCII-safe.
- SKILL.md + references/authoring-plans.md — `## SUBSLICE:` syntax + semantics (one level only;
  ordered children; parent-iff-all; nested `--usage`); global synced.

**🎉 WHOLE FEATURE DONE — "scalable picker + cursor" (4 parts, spec
`docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md`).** Part 1 (scalable picker
+ effort axis) · Part 2 (CursorExecutor) · Part 3 (opt-in per-slice review) · Part 4 (sub-slices).
All shipped subagent-driven, one part per sitting. ONE open item remains: cursor long-prompt
dispatch (cursor-agent v2026.06.12 defect — see the OPEN ITEM block below + [[project_cursor_dispatch_open_item]]).

**(prior) ✅ PART 3 of 4 SHIPPED — opt-in per-slice review mode; 281 passed**

**✅ PART 3/4 COMPLETE — Opt-in Per-Slice Review Mode (2026-06-15, commits 6f43a26→67d904f, 281
passed).** Subagent-driven, all 4 tasks 2-stage reviewed + a final SHIP integration review. Default
behavior is UNCHANGED (pick-once-and-stick / the S1b fix). Delivered:
- `src/cld/orchestrator.py` — `slice_pick_fn(task, default_spec) -> spec` callback on
  `run_plan_parallel` (and accepted as a no-op on legacy `run_plan`). Resolution order in
  `_resolve_spec`: **tag > pick_fn > default**; `slice_pick_fn=None` = current behavior. The
  resolved spec is threaded as `model=` into `deliver_slice`, so the LEDGER now records the actual
  per-slice spec (was hardcoded default). `_effort_of(spec)` parses the `@effort` suffix. NOTE
  comment warns the callback runs in ThreadPoolExecutor worker threads.
- `src/cld/ledger.py` — `LedgerEntry.effort` field (mirrors `model`: field+load+set+save);
  backward-compatible (old ledgers load with effort=None). `model` keeps the FULL spec (incl
  `@effort`); `effort` is the parsed suffix — the two agree (one source).
- `skill/scripts/run_delivery.py` — `--per-slice-pick` flag (default OFF) + `make_slice_pick_fn`:
  off→None (S1b); on→a callback that falls back to default when non-interactive (so `--step`/
  automation never blocks) and SERIALIZES the interactive prompt under a `threading.Lock` (safe
  under the worker-thread call site). Wired into BOTH `run_plan_parallel` call sites.
- SKILL.md: per-slice review mode rules (OFF by default; "do NOT enable on your own initiative";
  tagged slices honored silently even when ON; choice recorded in ledger/`--usage`); flag added to
  the command example; global synced (byte-identical).

**(prior) ✅ PART 2 of 4 SHIPPED — CursorExecutor; 265 passed. Dispatch open item.**

**✅ PART 2/4 COMPLETE — CursorExecutor (2026-06-14, 265 passed, 1 deselected).** Subagent-driven,
all 8 tasks committed. Delivered:
- `src/cld/executors/cursor.py` — `CursorExecutor` (argv `-p --output-format json --workspace
  --model --force --trust`, effort→model-suffix), `_cursor_cmd` (CURSOR_AGENT_CMD → versioned
  `.cmd` on Windows → fallback), `_default_runner` (utf-8/replace), `parse_cursor_usage`
  (single-object JSON, camelCase→snake, total=in+out). Registered in `executors/__init__.py`
  (`KNOWN_EXECUTORS` now includes "cursor").
- `src/cld/models.py` — `list_cursor_models` + cursor effort-grouping in `build_model_index`
  (138 raw → 33 base models), `resolve_composer_default` (tracks current Composer), Composer
  catalog entry `cursor:composer-2.5`, `_spec_for` passes cursor `:` specs through.
- `src/cld/usage.py` — `parse_cursor_about` + conditional `## Cursor account` block (tier +
  default model, server-side-usage pointer; only when a `cursor:*` slice is in the ledger).
  `run_delivery.py --usage` shells `cursor-agent about` (timeout-guarded) and passes it in.
- SKILL.md: cursor in the `--executor`/picker mapping + usage view + headless-only note; global synced.

**⚠️ OPEN ITEM — Cursor long-prompt dispatch (deferred, NOT a code bug). RE-VERIFIED STILL BROKEN
2026-06-15** (version unchanged at 2026.06.12-...-f6aba9a; short prompt rc=0 in ~7s, long prompt via
`.cmd` fails fast on "Workspace Trust Required" (flags mangled), long prompt via direct-node hangs to
150s timeout = the core defect. Detail in `docs/notes/cursor-cli-notes.md`.) Root-caused live as a
**cursor-agent v2026.06.12 defect**: long multi-line `-p` prompts hang without a TTY (matches
community "-p hangs indefinitely" reports). SHORT dispatches work (`--list-models`, `about`,
feasibility). All Part-2 NON-dispatch machinery is built + tested; CursorExecutor cannot run a REAL
(long-prompt) slice on this cursor version. The one Composer-via-CLI dogfood (T5
`resolve_composer_default`) FELL BACK TO GEMINI per the plan's stated fallback — **Composer NOT yet
proven headless** (no evidence-store verdict recorded). Revisit when cursor ships a fix / a
`--prompt-file` input. Working short-prompt primitive: `node.exe index.js <argv>` +
`CURSOR_INVOKED_AS` env + `stdin=DEVNULL`. Detail: `docs/notes/cursor-cli-notes.md`.

**(prior) ✅ PART 1 of 4 SHIPPED — scalable picker + effort axis; 246 passed**

**✅ PART 1/4 COMPLETE — Scalable Picker + Effort Axis (2026-06-14, commits 4e60cc2→ff5a240, 246
passed).** Subagent-driven, all tasks green + 2-stage reviewed. Delivered in `src/cld/models.py`:
`ModelChoice` index record + expanded `KNOWN_PROVIDERS` (grok/kimi/qwen/glm/minimax, `_provider_of`
now strips version digits); `build_model_index` (Gemini dogfood) unifying gemini+opencode(+cursor
tuples) with evidence overlay; `browse_filter` (headless-only default) + `rank_provider_models`
(proven-first top-N) (Gemini dogfood); `render_executor_level`/`render_provider_level`/
`render_model_level`/`render_effort_level` drill-down (Claude, verbatim-guard surface);
`search_models` (Gemini dogfood — "compo"→Composer, "3.1"→all gemini-3.1 routings labeled);
`spec_with_effort` + `parse_executor_spec` `@effort` split (Claude). **Review caught a latent bug:**
`@effort` specs crashed opencode/gemini (unexpected kwarg) — fixed (6f81bd5): both now accept
`effort` (opencode→`--variant`, gemini ignores). SKILL.md browse section rewritten to the drill-down
+ search + effort + headless-filter flow; global synced.

**NEXT: nothing in flight — the 4-part scalable-picker-and-cursor feature is COMPLETE.** Candidate
follow-ups (user's choice, none started): (1) revisit the cursor long-prompt dispatch open item when
cursor-agent ships a fix / a `--prompt-file` input (then prove Composer headless via the deferred
dogfood); (2) a live end-to-end build exercising the new picker + per-slice review + sub-slices on a
real plan; (3) add kimi-k2.7 to the live shortlist once it appears in `opencode models`.

---

**(superseded)** 📋 Scalable-picker + Cursor planned, 5 plans committed — Part 1 now shipped.

**📋 NEXT FEATURE PLANNED, NOT STARTED (2026-06-14, commit 7b299f6) — DO NOT BUILD until the user
says go.** Scalable picker + effort axis + Cursor executor + per-slice review + sub-slices.
Spec: `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md` (4 parts).
Master plan: `docs/superpowers/plans/2026-06-14-scalable-picker-cursor-MASTER.md`. Multi-sitting,
build order **Part 1 → 2 → 3 → 4**, each its own sitting-sized plan:
- **Next task when given go-ahead: Part 1, Task 1** (`2026-06-14-part1-scalable-picker.md` —
  ModelChoice + expanded provider detection).
- **Execution prefs (user-chosen 2026-06-14):** SUBAGENT-DRIVEN (fresh subagent per task +
  two-stage review: spec-compliance then code-quality) and **ONE PART PER SITTING** — pause and
  update STATUS between Parts; do NOT roll into the next Part without a fresh go-ahead.
- Cursor feasibility already PROVEN live + installed + logged in (jhesham, Pro); broken top-level
  launcher shim replaced with a working one (`*.broken-bak` backups kept). kimi-k2.6 + deepseek-v4-pro
  PROVEN in the evidence store. Composer-2.5 to be proven via the ONE Part-2 CLI dogfood.
- Dogfood routing: ~90% gemini workhorse; one small Part-2 slice → cursor:composer-2.5 via CLI.
- **Part 4 caveat:** run its Task 2 (SliceTask fields) BEFORE Task 1 (the dogfooded parser).

---

**(2026-06-13)** ✅ Multi-LLM build controls SHIPPED + 2 opencode bugs fixed — 226 passed

**✅ MULTI-LLM BUILD CONTROLS — BOTH PLANS SHIPPED (2026-06-13).** Spec 4d60a2a→e79afc1,
plans b377868. Executed subagent-driven (fresh subagent per task + 2-stage review).
- **Plan 1 (per-slice executor)** commits bc23365→6fa4b88: `SliceTask.executor` field, slice.py
  parses `executor:`, `run_plan_parallel` resolves per-slice via `executor_factory` (mixed
  executors in one layer; unknown spec fails only that slice), run_delivery wiring, SKILL.md
  picker-once-and-stick + bounded per-slice proposals + curated shortlist (kimi-k2.6 +
  claude-sonnet-4-6 added). Catalog dogfooded to Gemini.
- **Plan 2 (usage view)** commits 5e37c33→b370637: LedgerEntry gains model/token_usage/cost
  (both run_plan + run_plan_parallel persist it), `cld/usage.py` (parse_opencode_stats +
  render_usage_table), `run_delivery.py --usage` + `cross-llm-delivery-usage` skill. Markdown
  table = per-build ledger + `opencode stats` aggregate; renders in CLI + VS Code.
- **TWO OpenCode bugs fixed** (found via the live picker experiment): (1) the `opencode.cmd` npm
  shim mangles long multi-line prompts via `cmd.exe /c` → `_oc_cmd` now invokes the real
  `opencode.exe` behind the shim (commit 7e8f1a5); (2) `capture_diff` reported `__pycache__/.pyc`
  as changed files → judge falsely flagged disallowed edits → false known-bad; now filtered
  (commit f771c86). Write-up: `docs/opencode-dispatch-bug-feedback.md`.
- **DOGFOOD: both Plan-2 pure-logic slices (T3 parse_opencode_stats, T4 render_usage_table) built
  by OpenCode `deepseek-v4-pro`** through the now-fixed executor — proving it on real feature work.
- **kimi-k2.6 = PROVEN headless** (finally, after the multi-session saga) — recorded durably in
  `~/.cld/validation-evidence.json`; the evidence overlay shows it `proven` (no warning) in the
  picker. deepseek-v4-pro also proven via the dogfoods.

---

**(earlier 2026-06-13)** ✅ RESOLVED: opencode `-m` WORKS; false blocker debunked — 204 passed

**📋 NEXT (candidates — nothing in flight; user testing the skill on other projects 2026-06-13):**
The 3 previously-captured items are ALL SHIPPED this session (per-slice executor, picker frequency,
usage view — see the top block). Remaining open EXECUTOR adapters (pluggable infra is done; each is
just "write one adapter satisfying the Executor protocol"):
- **Cursor executor (`cursor-agent`)** — user's leading candidate, but GATE FIRST: the original
  2026-06-08 design rejected cursor-agent because it needed WSL and couldn't run headless on this
  Windows Server box. Before any build, do a zero-cost check of whether `cursor` CLI can dispatch
  headless on Windows NOW. If it still needs WSL, it's a dead end like codex.
- **Claude-headless executor** (`claude -p`) — the lead model as an executor; no WSL concern; noted
  as a future adapter alongside cursor.
- **Codex — EXCLUDED** (no clean headless mode).
Stale "future" notes `docs/notes/future-per-slice-executor-by-complexity.md` + `future-usage-modal.md`
are now IMPLEMENTED (kept for design history).

**✅ OPENCODE `-m` MODEL SELECTION WORKS (2026-06-13).** The earlier "🔴 blocker" was FALSE.
PROVEN at $0 (dashboard billed-model = ground truth): six dispatches, every one billed the model
passed via `-m` — including a run with the global config PINNED to deepseek + `-m mimo` → billed
**mimo** (config does NOT override `-m` either). The one anomaly (2:58 mimo→deepseek) was corruption
from a leaked server + dispatch-guard at that instant, never reproduced clean. **GOTCHA: a model's
self-reported id is unreliable (one mimo run claimed "mimo-v2-pro-free") — trust the BILLED model,
not the text reply.** That mis-led the prior diagnosis. **Implication: picker / `--executor
opencode:<model>` / recommend / validate_model all correctly control the model — NO executor change
needed for selection.** Full write-up: `docs/notes/opencode-model-selection-blocker.md`. Real fixes
that landed (correct): serve+attach isolation, leak-proof tree-kill teardown, utf-8 decode, dispatch
guard, durable evidence store. **kimi-k2.6 headless still UNVALIDATED** — now achievable; one clean
validation (config empty, opencode TUI closed) gets the honest verdict.

---

**(earlier 2026-06-13)** ✅ Durable evidence store + (mis-named) attach fixes — 203 passed

**✅ DURABLE EVIDENCE STORE + ATTACH-HIJACK FIXES (2026-06-13, commits d21aea1+64150df — 203
passed).** (1) **CRITICAL find:** a running opencode TUI captures `opencode run` (attach mode) —
a kimi-k2.6 request was served by the TUI's `build·claude-opus-4-8` (premium, billed) in the
TUI's directory, editing unrelated worktrees (cld-live-test wt + our smoketest; both cleaned).
Fixes: bare `--port` (fresh local server) + dispatch guard (no `step_finish` JSONL event →
ok=False, no diff trusted). `--dir` exists but means "path on remote server" when attached.
(2) **Durable evidence store** (user-directed, supersedes session-only): `cld/evidence.py`
EvidenceStore → `~/.cld/validation-evidence.json`; `resolve_and_validate(evidence_store=,
force_revalidate=)` consults before spending + records verdicts; `recommend`/`browse_models`
take `evidence=` overlay. **kimi-k2.6 headless = UNRESOLVED** — cannot validate while a TUI
is running (all 3 attempts hijacked); revalidate with the TUI closed; nothing recorded.

**✅ BROWSE PICKER + VALIDATE-ON-DEMAND COMPLETE (2026-06-13, commits 61ceaa3→ba6e8dd — 192
passed).** Spec 338e9bc, plan e004785. `browse_models`/`render_browse_list` (full 46-model
grouped browse, verbatim-render guard), `resolve_and_validate` gate (untested pick → real-slice
validation w/ "please wait" progress msg; metered → cost confirm; known-bad → decline +
session-only mark + re-present), `recommend(session_known_bad=...)`. T1 was a Gemini dogfood;
T2–T5 were applied externally to the working tree mid-session and Claude-judged green.
**Live finds from validating `opencode/kimi-k2.6`:** (1) all subprocess runners now decode
utf-8/replace — kimi emitted 0x90, killing the cp1252 reader thread (the first verdict was
corrupted by our own harness); (2) `validate_model` now returns `untested` (not `known-bad`)
on a failed dispatch. **Honest verdict after fixes: kimi-k2.6 = known-bad for headless
slice-building** (dispatch OK, ran pytest, never wrote calc.py — the "explores but doesn't
write code" failure mode). Session-only; re-validatable. Validate-on-demand proved itself live.

---

**(Earlier)** ✅ OpenCode executor + model-picker SHIPPED — 9 tasks, 164 passed (2026-06-12)

**✅ OPENCODE EXECUTOR + MODEL PICKER COMPLETE (2026-06-12, commits 74c3239→bd9576b — 164 passed).**
Added OpenCode CLI as a 3rd executor (`KNOWN_EXECUTORS = gemini, composer, opencode`) with a full
interactive model-picker, all 9 TDD tasks committed one-per-task. Design `aa7f0b8`, plan `bfb00be`.
- **T1** captured the REAL `opencode --format json` shape — it's **JSONL** (newline-delimited
  events), tokens at `step_finish → part.tokens {total,input,output,reasoning,cache}`, `part.cost`
  per step. Sample + notes in `docs/notes/opencode-run-sample.json` / `opencode-cli-notes.md`.
- **T2** shared `capture_diff` (`src/cld/executors/_capture.py`) — Gemini + OpenCode both reuse it.
- **T3** `OpenCodeExecutor` seam (`src/cld/executors/opencode.py`): `opencode run <prompt> -m
  <provider/model> --format json --dir <wt>`, Windows `opencode.cmd`/`OPENCODE_CLI_CMD`.
- **T4** `parse_opencode_usage` (JSONL, sums step_finish events) — **Gemini dogfood**, judged green.
- **T5** registry entry. **T6** `src/cld/models.py` catalog + `list_models` — **Gemini dogfood**.
- **T7** `recommend()` (filter→bucket→annotate, default=proven workhorse, premium→confirm_cost,
  untested→warning) — **OpenCode SELF-DOGFOOD** via `opencode/deepseek-v4-flash-free`, judged green.
  This is the milestone: OpenCode built a slice through its own now-proven executor.
- **T8** `src/cld/validate.py` `validate_model` — evidence-backed headless validation (throwaway
  real-git repo + trivial add(a,b) slice + real scoped pytest as judge → proven/known-bad/untested).
- **T9** SKILL.md interactive picker (default workhorse, cost-confirm on premium, warn+offer-validate
  on untested) + global skill synced. `cld` is an editable install so the package auto-picks-up.
- **Dogfood scorecard: 17/17 grade A** (T4, T6 Gemini; T7 OpenCode/deepseek — all $0, judged by
  independent pytest, none trusted on self-report). All dogfood dispatches cost $0 (flat/free tiers).
- **Safe by inheritance held:** OpenCode inherits Bug A/B, `--step`, judge timeout, feedback loop —
  it only adds the "type the code" half. No core (protocol/judge/ledger/DAG/orchestrator) changed.

---

**(Earlier 2026-06-12)** 🐛 TWO real bugs found from a live advisor run — now fixed (below).

**✅ TWO BUGS FIXED (2026-06-12, commit 483826e — 144 passed).** Bug A: worktree.py now resolves repo_dir to abspath → `--repo .` yields a clean sibling `<abs>-wt-<branch>`, never `.-wt-*` inside the repo (3 tests). Bug B (the token-drain): `deliver_slice` passes `task.acceptance_test_path` to `test_runner`; `pytest_test_runner` runs ONLY that test (not the whole suite — which billed `claude -p` in the advisor repo and let a hang freeze the build), + a 600s per-judge timeout; backward-compatible with 1-arg runners (4 tests). **rac-agent S7 / advisor build left ENTIRELY to the advisor thread per user — cld made NO changes to rac-agent.** Below is the original bug write-up (kept for reference):

**(ORIGINAL, NOW FIXED) FIX TWO REAL `cld` BUGS** found when a live advisor build (rac-agent S7 merge_context) failed 3× and stranded — Claude tokens drained with no build progress. Diagnosed: the build process had already died (~6h frozen ledger); recovered rac-agent (deleted orphaned `.-wt-slice-S6a/S6c` dirs + empty `slice-S7` branch). The two bugs (both confirmed in code):

### BUG A — malformed worktree path when `--repo .` (HIGH)
`src/cld/worktree.py` line 5: `path = f"{repo_dir}-wt-{branch}"`. With `repo_dir="."` this yields `.-wt-slice-S7` — a dir literally named `.-wt-...` INSIDE the repo (not a clean sibling). Pollutes the repo + confuses git. **Fix:** build the worktree path with `os.path` against the repo's PARENT (resolve `repo_dir` to an absolute path first, then put `<abspath>-wt-<branch>` as a real sibling, or use a dedicated temp/worktrees dir). Add a test: `--repo .` (and a relative path) produce a sibling-style path, never `.-wt-*` inside the repo.

### BUG B — judge runs the WHOLE suite, not the slice's acceptance test (HIGH — the token-drain mechanism)
`skill/scripts/run_delivery.py::pytest_test_runner` runs `python -m pytest -q` = the ENTIRE target-repo suite in the worktree, NOT the slice's `acceptance_test_path`. Consequences: (1) in a repo whose suite calls a paid LLM (rac-agent advisor uses `run_via_cli` → headless `claude -p`), EVERY judge-run bills Claude — this is where the tokens went; (2) a single hang in the full suite freezes the whole build (what stranded S7). **Fix:** `pytest_test_runner` (and/or `deliver_slice`'s judge wiring) must run ONLY `task.acceptance_test_path` (e.g. `pytest <acceptance_test_path> -q`), not the whole suite. Pass the acceptance path through to the runner. Add a test asserting the runner is invoked with the slice's specific test path, not a bare suite run. (Optional hardening: a per-judge timeout so a hung test can't freeze a build.)

**Both are exactly the "judge-side cost/safety" class. After fixing: re-run advisor S7 cleanly (it failed legitimately — merge_context port didn't pass; no code was collected, slice-S7 branch was empty). Then resume advisor Sitting B.**

---

**Context-lean orchestration is BUILT (2026-06-11):** ✅ **Context-lean interactive orchestration is BUILT (2026-06-11).** The token-drain fix shipped as the `--step` batch-step feature: lead agent runs ONE DAG layer per invocation, gets a ~10-line summary (exit 0/2/3), re-invokes to advance; raw output → `.cld/<id>/detail.json` (off agent context); concurrent fan-out + worktree isolation preserved; SKILL.md has the loop + cache-aware rules. **7 tasks, all TDD, all committed; 137 passed.** Dogfood scorecard now 14/14 grade A (T2/T3/T4 were Gemini dogfoods). Plan: `docs/superpowers/plans/2026-06-10-context-lean-orchestration-plan.md`.

**NEXT options (user's choice):** (1) **Resume the advisor build** (rac-agent Sitting B, S4–S5) — now using `--step` so it's context-lean; transcribe advisor plan to cld `## SLICE:` format = Claude Step 1. (2) ~~OpenCode CLI 2nd executor~~ ✅ DONE (see top). (3) **Live end-to-end test** of the full skill on a real plan via `--step`. (4) **Run a real `--step` build through `--executor opencode:...`** to prove the picker path end-to-end on a non-trivial plan (T1-T9 proved the units + one self-dogfood slice; a full multi-layer OpenCode build is the remaining live proof).

**Context-lean orchestration — tasks shipped (all committed):**
- ✅ T1 PlanResult.details + DeliverResult files/diff_lines (Claude, 52eb699)
- ✅ T2 summarize_layer + T3 classify_gate — `src/cld/summary.py` (DOGFOOD grade A, merged)
- ✅ T4 next_pending_layer (DOGFOOD grade A, merged)
- ✅ T5 `--step` mode + write_artifacts (Claude, b4dffc8)
- ✅ T6 SKILL.md batch-step loop + cache rules (Claude, a9efc13)
- ✅ T7 real-git step-through integration test (Claude, 254cc06)
- This is ~the same split as BUG 1, which worked well. **This feature is itself dogfood-able — fitting, since it's a cld feature.**

---


**Next task:** User's choice from "NEXT options" above. Leading candidate: a live multi-layer
`--step` build via `--executor opencode:opencode/deepseek-v4-flash-free` to prove the picker path
end-to-end. (Advisor build Sitting B remains an option — READ THE TOKEN-DRAIN FINDING FIRST, below.)

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
