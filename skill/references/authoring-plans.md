# Authoring good plans (slices + contracts)

The quality of a cross-llm-delivery run is determined almost entirely by the plan. The
executor is reliable at *making a clear contract pass*; it cannot rescue a vague one. This
is where Claude's leverage lives — spend the thinking here.

## Vertical slices, not horizontal layers

Each slice must be **thin but end-to-end and independently testable**. A horizontal layer
(e.g. "all the dataclasses") can't be validated until other layers exist, which breaks the
judge loop. A vertical slice (e.g. "the ledger: schema + atomic save + load") has its own
passing/failing test and can be judged in isolation.

## Stable interface contracts between slices

Fix the seams up front so a bad slice's rework stays *local* and can't cascade. Name the
types/functions a slice exposes, and reference them consistently across dependent slices.
For a slice that others depend on, its contract is part of *their* acceptance too.

## Acceptance tests written before handoff (TDD-flavored)

Author the failing test first and commit it. It is the objective contract the executor is
judged against — this is what makes judging cheap and rework local. The `brief` should tell
the executor exactly what to implement and which files it may touch; the test tells it when
it's done.

## The injectable-boundary rule

All model/tool/subprocess/git calls in a slice must go through an **injected/mockable
boundary** (dependency injection), never hardcoded. This keeps deterministic tests
deterministic (tests pass a fake), and it's how the whole engine stays testable without live
calls. State this rule in the brief for any slice that touches I/O.

## Right-sizing

- Big enough that executor implementation tokens dwarf Claude's spec + judge tokens.
- Small enough to stay independently testable and cap the blast radius of a bad slice.
- Empirically, even "real" modules are often 30–120 lines — that's fine; the win on a
  flat-rate executor is from $0-marginal typing, not from giant single dispatches.

## Dependencies / the DAG

List each slice's `deps`. Independent slices (no shared deps) run in parallel; dependents
wait for their layer. Avoid cycles (the DAG scheduler raises on them). Prefer a wide, shallow
DAG (more parallelism) over a long chain where possible.

## Slice brief checklist

A good `brief` states: what to implement, the exact public names/contract, the allowed files,
the injectable boundaries, "do not edit the test file", and any design rules the judge will
enforce. Pin anything the executor might otherwise guess (exact import paths, current model
ids, library class names) — guessing is the main failure mode.
