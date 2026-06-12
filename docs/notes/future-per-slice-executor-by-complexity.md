# FUTURE: per-slice executor selection by complexity (captured 2026-06-13)

**User request:** "I'd like to be able to swap models by slice, based on how complex the
session agent has assessed that slice/task could potentially be (more complex build → more
sophisticated agent)." Route each slice to the right-cost model by its difficulty — the core
comparative-advantage premise of the system, applied per slice instead of per build.

## Current state (the foundation + the gap)

- SKILL.md (line ~182) ALREADY promises: "a per-slice `executor:` field supports 'heavy model
  on this one slice'." **But it is NOT implemented:** `src/cld/plan/slice.py` does not parse an
  `executor:` field, and `SliceTask` (`src/cld/executors/base.py`) has no `executor`/`model`
  attribute. So the docs over-promise — close this gap as part of the feature.
- The orchestrator picks ONE executor for the whole `run_plan_parallel` call (per build), not
  per slice. `run_delivery.py` resolves a single `--executor` and passes one executor object in.

## Proposed shape (to brainstorm next, not yet designed)

Two layers:

1. **Plan-level override (explicit).** Let a `## SLICE:` block carry an optional `executor:`
   line (e.g. `executor: opencode:opencode/claude-opus-4-8`). `slice.py` parses it onto
   `SliceTask`; the orchestrator builds/uses that executor for THAT slice, falling back to the
   build default otherwise. This is the smaller, deterministic primitive — do this first.

2. **Agent complexity assessment (the new idea).** Before dispatching a slice, the lead agent
   rates its complexity (e.g. trivial / standard / hard) from the brief + files + contract, and
   maps that to an executor tier: trivial/standard → the $0 flat workhorse; hard → a more capable
   (metered) model. Surface the assessment + chosen model to the user (consistent with the
   "user picks" rule — propose, let them confirm/override). Could reuse the picker's tiers
   (workhorse / heavy / quick from `recommend`/the catalog's `capability_class`).

## Open design questions (for the brainstorm)

- Who assigns complexity — the planning agent at plan-authoring time (writes `executor:` into the
  plan), or the lead agent at dispatch time (dynamic)? Or both (plan hint + dispatch confirm)?
- Cost guardrail: a "hard" rating that picks a premium-metered model must still hit the existing
  cost-confirm gate. Don't let auto-escalation silently spend.
- How does this interact with the per-build picker + the "once per build, stick" frequency rule
  (also still open — see below)? Likely: build default is the floor; per-slice can ESCALATE
  (with confirm for metered), agent proposes, user can veto.
- Validation: a per-slice metered model that's `untested` should still go through
  `resolve_and_validate` before its slice runs.
- Parallel layers: slices in one DAG layer could use DIFFERENT executors concurrently — the
  orchestrator's `run_plan_parallel` must construct the right executor per slice, not one shared.

## Related still-open item

**Picker frequency** (raised same session): SKILL.md says "present before the first dispatch"
but agents re-trigger the picker per slice/re-dispatch (seen on S1b). Decide: ask ONCE per build
and stick (only re-ask on explicit "change executor") vs. re-ask on re-dispatch. This per-slice
feature should be designed together with the frequency rule — they're the same surface.

## Why it fits

The system already routes bulk work to a cheap executor by comparative advantage. Per-slice
selection extends that from build-granularity to slice-granularity, which is strictly more
efficient: most slices stay on the $0 workhorse, only the genuinely hard ones spend on a
stronger model — and only with the user's confirmation.
