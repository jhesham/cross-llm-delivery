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

## Sub-slices (one level)

A `## SLICE:` may contain one level of `## SUBSLICE: <id>` blocks. Each sub-slice has the same
fields as a slice (`brief`, `files`, `acceptance_test_path`, `deps`, and an optional
`executor:`/`@effort` tag) and is written directly under its parent in the plan markdown:

```
## SLICE: P1
brief: build the widget end-to-end
files: src/widget.py
acceptance_test_path: tests/test_widget.py
deps:

## SUBSLICE: P1a
brief: the parsing half
files: src/widget_parse.py
acceptance_test_path: tests/test_widget.py::test_parse
executor: cursor:claude-opus-4-8@medium

## SUBSLICE: P1b
brief: the rendering half
files: src/widget_render.py
acceptance_test_path: tests/test_widget.py::test_render
```

Semantics:
- Sub-slices run as **ordered children** under the parent (sequentially, in document order) — not
  fanned out. Ordering is positional, so sub-slices do not use `deps` among themselves.
- Each sub-slice is **independently routed**: its own `executor:`/`@effort` tag wins, else the build
  default, else the per-slice review prompt when that mode is on (`--per-slice-pick`).
- The **parent completes only when ALL its sub-slices are accepted**; a failed sub-slice fails only
  itself and leaves the parent incomplete (the failed child ids surface in the parent's failure detail).
- Each sub-slice is recorded in the ledger keyed `parent/child` (with its model + effort + tokens)
  and shows **nested under the parent** in `--usage`.
- **ONE level only** — no sub-sub-slices.

Use sub-slices to split one logical slice across different models/efforts (e.g. the cheap workhorse
for the mechanical half, a heavier model for the subtle half) while keeping it one unit in the DAG.

## Slice brief checklist

A good `brief` states: what to implement, the exact public names/contract, the allowed files,
the injectable boundaries, "do not edit the test file", and any design rules the judge will
enforce. Pin anything the executor might otherwise guess (exact import paths, current model
ids, library class names) — guessing is the main failure mode.
