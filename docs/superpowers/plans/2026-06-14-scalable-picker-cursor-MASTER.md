# Scalable Picker + Cursor + Per-Unit Routing — MASTER PLAN (multi-sitting)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. This is a MULTI-SITTING build — each Part below is its own sitting-sized plan file. Read STATUS.md "Next task" first, do ONE part (or as much as the token window allows), commit each task, update STATUS.md before stopping.

**Goal:** Make the model picker scale to 100+ models with effort selection and fuzzy search, add Cursor as a 4th executor, and let large builds route executor/model/effort per slice and per sub-slice.

**Spec:** `docs/superpowers/specs/2026-06-14-scalable-picker-and-cursor-design.md`

**Architecture:** Four independently-shippable parts, built in order. A unified `ModelChoice`
index (Part 1) is the keystone everything reads. Cursor (Part 2) feeds it. Per-slice review
(Part 3) and sub-slices (Part 4) extend the orchestrator/plan model. Each part keeps the full
suite green and is sliced TDD with builder tags.

**Tech Stack:** Python 3.11+ stdlib, pytest (fakes; no live LLM in default suite), the cursor /
opencode / gemini CLIs (live calls only in explicit, marked slices).

---

## Part plans (each = one sitting)

| Part | Plan file | What it delivers | Depends on |
|------|-----------|------------------|------------|
| **1** | `2026-06-14-part1-scalable-picker.md` | Unified model index + effort axis + headless filter + executor→provider→model→effort drill-down + fuzzy search. Built vs the current 46 opencode models. | none |
| **2** | `2026-06-14-part2-cursor-executor.md` | `CursorExecutor` + `list_cursor_models`/`resolve_composer_default` + `parse_cursor_usage` + catalog/registry + usage `## Cursor account` block. Feeds Part 1's index. Composer-via-CLI dogfood. | Part 1 |
| **3** | `2026-06-14-part3-per-slice-review.md` | Opt-in `--per-slice-pick` review mode (off by default; S1b "pick once stick" preserved); per-slice choice recorded in ledger. | Part 1 (picker), Plan-1 per-slice executor (shipped) |
| **4** | `2026-06-14-part4-sub-slices.md` | One-level `## SUBSLICE:` units: plan parse, orchestrator children, ledger attribution, review-mode prompt per sub-slice. | Parts 1+3 |

> **Part 4 task-order caveat:** its tasks are numbered by topic, not run-order. Run **Task 2
> (SliceTask fields) FIRST**, then Task 1 (the dogfooded parser, which needs those fields), then
> T3→T4→T5. The Part-4 plan states this inline too.

**Build order is strict:** 1 → 2 → 3 → 4. Each part ships green and is usable on its own
(Part 1 improves the existing picker even before Cursor; Part 3 works for gemini/opencode before
sub-slices exist).

## Dogfood routing (whole build)
~90% of dogfood slices → **gemini workhorse** (`gemini:gemini-3.1-pro-preview`, $0 flat, proven).
Pure-logic slices may also go to **opencode/deepseek-v4-pro** (proven). **Exactly ONE small late
slice → `cursor:composer-2.5` via the cursor CLI** (Part 2's `parse_cursor_about` or
`resolve_composer_default`) as the headless-proof Composer touchpoint — non-load-bearing.
Seams/registry/orchestrator/SKILL.md = Claude-direct.

## Resume protocol
- STATUS.md "Next task" names the current Part + task.
- Each task ends with: commit + STATUS update.
- A Part is "done" when its plan's Done-criteria pass + full suite green; then advance STATUS to
  the next Part.
- The picker is the project's single-source-of-truth surface — keep the "render verbatim, never
  hand-type options" guard in force across all parts.

## Done criteria (whole feature)
- Browse picker scales to 100+ models: headless-only by default, executor→provider→model→effort
  drill-down, fuzzy search ("compo"→Composer, "3.1"→all gemini-3.1 routings labeled).
- Effort is selectable (default = CLI's pre-selected) and maps to each CLI's form.
- Cursor is a working 4th executor; Composer is the dynamically-resolved Cursor default.
- `--per-slice-pick` lets a build revisit executor/model/effort per slice (off by default).
- Slices may contain one level of sub-slices, each independently routed + ledger-attributed.
- Full suite green throughout; backward-compatible (existing plans/behaviour unchanged when new
  features unused).
