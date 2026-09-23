# Codex-led cross-llm delivery workflow

This reference expands the entry skill: how Codex leads a build that a headless
provider executor implements slice by slice. Codex is the lead (decompose,
contract, judge, integrate); the provider CLI is the implementation executor.
Run commands from the installed skill directory with absolute plan and target
repository paths. The driver is vendored under that directory:

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> <command> [--json]
```

No package install and no source checkout are required; the engine is vendored
under `scripts/`. Prefer `--json` on every gate so the response is
machine-checkable, and act on the exit code.

## 1. Decompose the build into a plan (the lead's thinking)

Author a plan markdown with one block per slice. Each slice is thin but
end-to-end and independently testable, with a stable interface contract and a
failing acceptance test the executor must make pass. Express dependencies so
independent slices can run in parallel.

```
## SLICE: T1
brief: Implement <X> so that tests/test_x.py passes. <contract details,
  constraints, injectable boundaries, allowed files.>
files: src/x.py, tests/test_x.py
acceptance_test_path: tests/test_x.py
deps:

## SLICE: T2
brief: Implement <Y> ...
files: src/y.py
acceptance_test_path: tests/test_y.py
deps: T1
```

Author the acceptance tests first (committed, failing); they are the objective
contract the executor is judged against. Slices are vertical, not horizontal,
with injectable boundaries. Respect the user's existing project instructions
when writing contracts; never overwrite them.

## 2. Preview, then batch-step

Always preview the layering first, then drive the build one DAG layer at a time
so your context stays small and you can steer between phases:

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json
python scripts/run_delivery.py <plan.md> --repo <dir> --step --json [--workers N] [--executor <name>[:model][@effort]]
```

A step runs only the next pending layer (independent slices fan out
concurrently in isolated worktrees), then exits with a short summary. Read the
summary, relay it to the user, and act on the gate (exit code):

- 0: the operation succeeded; work remains.
- 2: execution/test failure or dependency defer; inspect the named evidence.
- 3: every slice is integrated and verified; review the recorded commit/ref.
- 4: lead repair is required; follow the repair loop below.
- 5: invalid plan/state, missing prerequisite, lock or policy block; resolve it.
- 6: accepted commits await integration before dependent dispatch.

For a cheap mid-run digest, poll `--status --json` between turns instead of
reading raw logs. Per-slice detail lives under `<dir>/.cld/runs/<run-id>/`;
open one evidence file only when the user asks for that slice.

## 3. Choosing the executor and model

Present the model shortlist once, before the first dispatch of a build, and let
the user pick; a default existing is not permission to choose on the user's
behalf. Do not silently choose or switch models. Skip the picker only when the
user already named an executor this session; then echo that choice and proceed.
The choice persists for all slices and re-dispatches of the build.

Build the picker from the engine helpers and render the options verbatim --
never hand-type, reorder, or recall them from memory:

```python
from cld.models import list_models, recommend, render_chat_picker
recs = recommend(available_ids=list_models())
print(render_chat_picker(recs))
```

Rules:

- The default is the provider's workhorse (see `references/provider.md`).
- For a premium-metered model, confirm that billed dispatches are covered by
  the user's existing authorization; ask if that is unclear. Declining falls
  back to the default only with the user's agreement.
- An untested model goes through `cld.validate.resolve_and_validate` (one
  trivial slice as judge) before any real build trusts it; metered validation
  requires authorization, which may already exist. Never claim discovery or capability has been verified
  when it has not.
- A slice may pin `executor: <name>:<model>` in its block; that slice runs on
  it silently. Untagged slices use the build default.

## 4. Acceptance and integration are separate

After acceptance, integrate the exact recorded commits with an explicit suite:

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <selector> --json
```

The engine merges in an owned worktree, verifies the frozen candidate, and
records its integration SHA. Subsequent slices branch from that SHA; the user's
checkout is untouched. Failed or unintegrated dependencies block dispatch, and
repeating a published integration is a no-op.

## 5. The gate-4 repair loop (explicit authorization)

Gate 4 means a slice needs lead repair or an integration candidate
failed/conflicted. Failed worktrees are retained. Follow the user's existing
authorization and the host's active approval policy before editing source;
ask only if authorization is unclear. Never silently dispatch another paid attempt.

1. Read that attempt's diagnostics under `.cld/runs/<run-id>/`.
2. Fix the permitted source files in the recorded retained worktree; keep
   committed acceptance tests and protected inputs unchanged.
3. Verify the repair with the original plan:
   ```bash
   python scripts/run_delivery.py <plan.md> --repo <repo> --mark-repaired <slice_id> --ledger <path> --json
   ```
   This re-tests and collects a frozen repaired candidate in a new owned
   worktree. Exit 6 means accepted and awaiting integration.
4. Integrate with `--integrate --integration-tests <selector>`. For an
   integration conflict, resolve and commit in the retained integration
   worktree, then `--integrate --manual-integration <resolved-commit>`.
5. Continue with `--step` only after successful integration.

Repair verification and integration do not invoke the provider.

## 6. Telemetry and usage

Telemetry is always on and local: every build writes `<repo>/.cld/events.jsonl`;
read it with `--status --json`. Exporting to an OTLP backend is opt-in via env
vars. `--usage` renders a combined per-build and account usage table from the
ledger plus provider aggregate stats; re-run to refresh.

## Provider specifics

- `references/provider-setup.md` -- install and verify the executor CLI.
- `references/provider.md` -- locked invocation form, auth, cost, and platform
  notes for the selected provider.
