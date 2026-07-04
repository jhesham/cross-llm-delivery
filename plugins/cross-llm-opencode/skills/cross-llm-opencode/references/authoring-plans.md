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

### …but injectable boundaries need BOTH paths specified (or green code breaks live)

The rule above, alone, only ever exercises the **fake** path. An executor faithfully implements
exactly what the brief + test describe — so if the brief only describes the fake, you get code
that passes its test and fails on the first real run. This is the #1 source of post-build
refactor. For every injected boundary, the brief MUST pin all three of these:

1. **The real default.** Say exactly what the parameter falls back to when not injected — by
   module/callable. e.g. *"`bq=None` defaults to `tools.bigquery_cli.run`; it must NEVER be a
   `pass`/`raise`/`...` stub."* A boundary whose only test is the fake path has an **untested
   production path** — the most common silently-broken shape (`def f(x, *, bq=None): if bq is
   None: pass`).
2. **The real data shape.** Where a slice parses an external tool's output, pin the REAL field
   names from a **captured sample**, not your assumption. e.g. *"`bq ls --format=prettyjson`
   returns the table name in `.id` as `project:dataset.table`, NOT `.tableId`."* A fake encodes
   your assumption about the shape; if the assumption is wrong, the executor matches the wrong
   shape and every test still passes. Prefer at least one acceptance-test case built from a
   recorded real fixture, not only a hand-written fake — that is the only thing that catches a
   shape mismatch at executor time instead of at first live run.
3. **No placeholder logic.** Forbid `...` / `TODO` / stub literals in any code path the test
   does not execute (invalid SQL like `SELECT a, ... FROM t`, empty handlers). If the test
   can't reach it, the brief must describe it exactly so the executor writes the real thing.

Rule of thumb: **if the only proof a path works is a fake you wrote, that path is unverified.**

## Live-shape verification: add an integration slice built from REAL fixtures

Per-slice fakes are a known TDD blind spot: a whole plan of green slices can still break on real
data because every test encoded the same assumptions. Plan for it explicitly:

- Add a final **integration slice** whose acceptance test runs the real collectors/parsers
  against **recorded real fixtures** (capture each external tool's output ONCE, commit it), kept
  distinct from the per-slice fake tests. This fails shape/contract drift INSIDE the build.
- **An integration gate built from the same fakes proves nothing the unit tests didn't.** If your
  integration check reuses the per-slice fakes, it inherits their wrong assumptions — capture
  real fixtures for it, or it is theater.
- For slices that touch live systems, note it in the brief (e.g. a `touches-live` marker) so the
  real-default + real-shape rules above get extra scrutiny and a real-fixture test case.

## Right-sizing

- Big enough that executor implementation tokens dwarf Claude's spec + judge tokens.
- Small enough to stay independently testable and cap the blast radius of a bad slice.
- Empirically, even "real" modules are often 30–120 lines — that's fine; the win on a
  flat-rate executor is from $0-marginal typing, not from giant single dispatches.

## Dependencies / the DAG

List each slice's `deps`. Independent slices (no shared deps) run in parallel; dependents
wait for their layer. Avoid cycles (the DAG scheduler raises on them). Prefer a wide, shallow
DAG (more parallelism) over a long chain where possible.

## Complexity (routing hint)

Each slice carries an optional `complexity:` field that tells the router which rung of the
executor ladder to start on. Set it honestly — cheap escalation between rungs is automatic
and free, but a wrong-low guess adds a re-run cycle.

| Value | When to use it |
|----------|----------------|
| `easy` | Pure boilerplate or one well-specified function; a known pattern with no tricky logic or I/O; the executor could write it from the contract alone with no risk of subtle error. |
| `standard` | A typical module with real logic and a few integrated pieces. **Use this when you are unsure** — it is the default. |
| `complex` | Subtle algorithm, concurrency, gnarly edge cases, ambiguous spec, or high rework risk; even a good cheap model would likely struggle. Flagged `!` in the routing plan and routed to the workhorse; a failure escalates to orchestrator repair. |

**Rule: never downgrade to `easy` or `standard` to save money when unsure — default to
`standard`.** A wrong-low complexity guess only causes cheap-to-free escalations; the router
handles them automatically. The cost of underestimating is a re-run cycle, not a surprise bill.

```
## SLICE: T3
brief: Implement the retry backoff with jitter so tests/test_retry.py passes.
files: src/retry.py
acceptance_test_path: tests/test_retry.py
complexity: complex
deps: T1
```

If omitted, the router treats the slice as `standard`.

## Slice brief checklist

A good `brief` states: what to implement, the exact public names/contract, the allowed files,
the injectable boundaries, "do not edit the test file", and any design rules the judge will
enforce. Pin anything the executor might otherwise guess (exact import paths, current model
ids, library class names) — guessing is the main failure mode.
