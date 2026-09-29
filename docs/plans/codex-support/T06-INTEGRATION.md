# T06 integration and resume guide

Implemented in the source engine and CLI; generated plugin copies are updated in T12/T17.
T07 implements the structured test-result and exit-code protocol; see [current contract](T07-CONTRACT.md).

## Step mode

Commit the acceptance and integration tests before starting. Choose a scoped,
offline integration selector deliberately; CLD never selects the entire suite implicitly.

```powershell
python skill/scripts/run_delivery.py plan.md --repo D:\project --step --executor opencode:<verified-model-id>
python skill/scripts/run_delivery.py plan.md --repo D:\project --integrate --integration-tests tests/test_integration.py
python skill/scripts/run_delivery.py plan.md --repo D:\project --step --executor opencode:<verified-model-id>
```

`--step` accepts one layer. Exit 6 means accepted work awaits integration; it does
not mean build complete. A dependent is deferred with the dependency's current
status until its exact commit belongs to the verified integration base.
`--integrate` does not require or call a provider. It merges ready accepted commits
in sorted slice-ID order and tests the combined tree. The selector is persisted;
later integration calls may omit it. Changing it requires explicit reconciliation
or a new build. Integration selects only accepted slices whose dependencies are
already integrated; repeated calls can process preserved acceptance after reconciliation.

Whole-plan execution requires `--integration-tests <selector>` for multiple layers.
With that option it uses the same integration lifecycle between layers. Without
it, unattended multi-layer execution is blocked before dispatch. A single-layer
run without integration configuration leaves accepted commits awaiting integration.
Direct callers pass `integration_test_path` and optionally `integration_test_runner`
to `run_plan`/`run_plan_parallel`. Integration runners take `(directory, selector)`
and now return a structured TestRun. The authoritative `__CLD_PYTEST_RC__` marker
remains a compatibility adapter for injected pre-T07 runners. The production CLI
supplies a scoped pytest runner with an authoritative process return code.

## Evidence and isolation

Each integration reserves a unique worktree below the configured worktree root
(default `<repo>/.cld/worktrees`) and writes a journal below
`.cld/runs/<run-id>/integration/<transaction-id>/`. `outcome.json`, `baseline.txt`
and `candidate.txt` identify the base, exact accepted commits, merge candidate,
baseline outcome and test result. Conflict indexes and failed candidates remain
in their worktrees. Successful integration worktrees are retained too; cleanup
is manual using normal Git worktree commands after inspecting the recorded path.
No automatic reset, branch deletion or user checkout update occurs.

The suite runs first on the recorded base and then on a frozen candidate tree.
A failing assertion baseline is allowed so new feature tests can start red.
Collection/configuration errors are blocked. A failed candidate is labeled either
`layer regression` or `baseline failure persists`, according to the baseline result;
the logs retain individual failures. Passing prose with a nonzero process return
code, zero tests, protected-input changes or mutation of the frozen tree cannot
publish integration.

Only after suite success does CLD pin the exact merge commit at
`refs/cld/integration/<run-id>/<transaction-id>` and publish the ledger's
`integrated_sha`, `integrated_ref`, proof and integrated slice statuses together.
Before dependent dispatch, it verifies that proof/ref and exact commit ancestry.
Later slice worktrees start at that SHA. Advancing or editing the user's checkout
does not change the build base. `--new-build` or explicit reconciliation adopts
the current HEAD when creating a new run; reconciliation preserves unaffected
acceptance but requires fresh integration proof.

## Interrupted or failed integration

Re-run the same integration command. Already published integration is a no-op.
An interruption before passing leaves its journal/worktree and creates a fresh
attempt on retry. If tests passed and the immutable ref/journal were written but
the ledger write failed, retry reuses that commit, re-tests it, and publishes it
without creating another merge commit. Failed ledger writes restore in-memory
state as well. Do not delete ownership lock files; OS ownership releases on exit.

For a merge conflict, inspect the journal's worktree, resolve the files there, then
complete its merge commit. Supply that commit to the verification-only path:

```powershell
python skill/scripts/run_delivery.py plan.md --repo D:\project --integrate --manual-integration <resolved-commit-sha>
```

CLD verifies accepted-commit ancestry, protected inputs, allowed file scope and the
configured suite in another owned worktree before advancing state. An arbitrary
manual branch or `--mark-repaired` status is insufficient proof of integration.

From T07, integration failure returns 4; invalid state/configuration returns 5; 3 is
reserved for a fully integrated build, while 0 indicates more work remains after
an integration action. T07 adds verified repair marking and consistent exit,
telemetry and status gates. Versioned JSON machine output remains T11 work.
