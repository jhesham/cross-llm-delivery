# T07 plan, test-result and gate contract

The source engine/CLI implement this contract. Generated plugin copies are updated
in T12/T17. Schema-2 ledgers remain compatible; use the current engine for writes.

## Validated plan

A plan uses top-level `## SLICE: <id>` blocks. Each requires a nonempty single-line
`brief` and an `acceptance_test_path`. `files`, `deps` and `protected_inputs` are
comma-separated literal lists. Existing `executor`, `complexity` (easy, standard,
complex) and boolean `allow_already_satisfied` fields remain supported. Markdown
preambles/headings and fenced plan wrappers are allowed. Duplicate IDs/fields,
empty or unsafe IDs, unknown fields/dependencies, cycles, missing selectors,
SUBSLICE blocks and multiline brief syntax are rejected with line diagnostics.

IDs use letters, numbers, dots, underscores and hyphens, beginning with a letter or
number. Build artifact names are reserved. Paths are exact portable repository
paths with forward slashes; spaces are literal. Absolute paths, drive/ADS colons,
backslashes, traversal and Git-directory components are rejected. Do not use shell
quoting around list entries. A comma in a filename is not representable in this
list syntax. Allowed files grant edit scope, not permission to change protected
inputs: selected acceptance inputs, conventional tests, pytest/config files and
explicit protected_inputs remain unchanged even when listed in files.

Selectors accept one relative file/directory/node ID, optionally `-k <expression>`.
Quote a path with spaces when adding `-k`, for example
`"tests folder/test_api.py" -k "ready and not slow"`. Bare paths containing spaces
remain one argument. Multiple paths, arbitrary pytest flags and empty selectors
are rejected. Inputs must exist in the committed baseline before execution.

`--dry-run` validates and layers the plan without Git, provider discovery or state
writes. Direct production APIs validate the complete plan too; subset dispatch
must supply plan_slices and each selected task must match its stored fingerprint.
DAG helpers reject dependency-only phantom nodes.

## Structured test results

Production runners return `cld.test_run.TestRun` with returncode, captured output,
optional log_path, timed_out, error, candidate_id and optional tests_run count.
The engine binds frozen tests to their actual Git tree ID and rejects mismatched
identities. Attempt journals save text and JSON result sidecars with their log path.
Timeout/launch failures retain partial output and cannot pass.

Return code 0 is authoritative, even if no pytest summary is printed. Nonzero,
missing or interrupted return codes, timeout/error flags and explicit zero test
counts cannot pass. Actual pytest zero-collection results use return code 5.
Parsed test counts and failure names remain diagnostics, not pass/fail authority.
Slice acceptance, integration and model validation probes use this rule. A red
baseline must still be identifiable assertion failures, not collection/configuration
errors. Candidate and protected-input checks remain independent of test success.

`legacy_result` adapts injected text runners. An anchored
`__CLD_PYTEST_RC__=<integer>` transport prefix is supported for pre-T07 callers;
plain passing prose is rejected. Only explicit simulation or an explicit
`legacy_result(text, allow_prose=True)` adapter may infer a synthetic verdict from
prose. Production subprocess output is a TestRun, so a test printing a fake RC
marker cannot override the real process code.

## Exit codes and next actions

| Code | Meaning | Next action |
|---|---|---|
| 0 | Requested operation succeeded; work remains | Follow recorded state; dry-run/status also use 0 |
| 2 | Slice execution/test failed or dependency-deferred | Inspect evidence; retry within policy |
| 3 | Every slice integrated and the integration proof verified | Report commit/ref; do not dispatch more work |
| 4 | Slice lead repair or integration repair required | Fix retained candidate and reverify |
| 5 | Invalid plan/state, missing prerequisite, lock or policy block | Resolve the stated block before dispatch |
| 6 | Accepted work awaits integration | Run --integrate with the configured suite |

Step and whole-plan mode use the same classifier. Repair and integration failure
cannot become success because the failed/deferred list happens to be empty.
Quota admission and active-owner blocks use 5. Dependent slices missing integrated
dependencies use 2 with an explicit reason. Code 6 never means build complete.
Human summaries avoid completion claims on failure/defer/repair. Telemetry records
operation_done with gate and gate_code; run_done is reserved for integrated
completion. Status overlays recorded ledger state so stale event history cannot
hide pending integration/repair. A read-only status command still exits 0 when the
read itself succeeds. Versioned JSON output and host packaging remain T11/T12 work.

## Verified repair

Use the original plan and repository:

```powershell
python skill/scripts/run_delivery.py plan.md --repo D:\project --mark-repaired A
```

A failed/needs_repair slice must have matching run/task evidence and a retained
owned worktree. Edit allowed source files in that worktree. The command validates
dependency/base/ownership, captures the repaired tree, runs baseline and frozen
acceptance tests in a new owned worktree, and checks collection before setting
accepted + intervened. It does not invoke a provider or modify the user checkout.
Protected-input edits, missing evidence or stale bases are blocked. Failed tests
remain needs_repair with evidence and a retained candidate. A failed final ledger
write leaves the verified collection reachable and the in-memory entry unchanged.

A successful repair returns 6: integrate it before dispatching dependents. A
needs_repair slice is not automatically redispatched by --step. For integration
conflicts, resolve/commit in the recorded integration worktree and pass
--integrate --manual-integration <commit>; ancestry and suite verification remain
mandatory. See [T06 integration/recovery guide](T06-INTEGRATION.md).

No live validation/model dispatch is needed for these tests. T08/T09 still gate
process bounding and provider validation before Kimi K3/OpenCode dogfooding.
