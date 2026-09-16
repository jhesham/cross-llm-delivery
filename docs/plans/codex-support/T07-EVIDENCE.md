# T07 — validated plans and gate protocol evidence

Implemented/tested: 2026-09-16. Closed: 2026-09-17. Starting commit: `d30623e` (T06).
Branch: `refactor/codex-support`; closing subject starts `fix: T07`.
**T07 and M2 complete.** 609 distinct current offline tests verified across the full
run and follow-ups. Resolve the closing commit with
`git log -1 --format=%h --grep="^fix: T07 "`.

## Contract changes

- The parser validates IDs, fields, dependencies, cycles, complexity, selectors,
  literal paths and supported single-line syntax, with line diagnostics. Obsolete
  SUBSLICE and silent field overwrite/text loss are rejected. Dry-run needs no
  provider/Git/state writes. Production subset tasks must match the complete plan.
- TestRun carries authoritative process RC, captured output, timeout/error class,
  candidate identity, optional test count and log path. Slice/integration/validation
  use the same RC authority. Frozen-run text/JSON sidecars retain diagnostics and
  timeout output. Passing prose cannot override nonzero RC; missing summaries do
  not reject successful process results. Explicit legacy/simulation adapters remain.
- --mark-repaired verifies ownership, run/task/base identity, allowed/protected
  changes, baseline/frozen tests and checked collection in a new owned worktree.
  Only verified repair becomes accepted/intervened. It still requires integration.
  Failure and publication faults preserve evidence and do not claim acceptance.
- Step and whole-plan use the same exit table. Needs-repair slices stop without
  automatic provider retry. Integration failures return 4 and persist repair
  evidence. Quota/lock/policy blocks use 5; accepted work awaits integration at 6.
  Human summaries and recorded status no longer imply completion on a failed gate.
  Operation telemetry carries gate_code; run_done means integrated completion.

See [T07-CONTRACT.md](T07-CONTRACT.md) for CLI/API/state details and compatibility.
Source README and skill template were corrected for the integration/repair workflow;
committed plugin copies remain deferred to T12/T17. Versioned JSON output remains T11.

## Tests and review findings

`test_t07_contracts.py` covers malformed plans and source diagnostics, paths/selector
syntax, fenced/space-containing plans, all gate codes, missing-summary success,
nonzero RC with passing text, interrupted/timeout/error/zero-collection results,
identity mismatches, explicit compatibility adapters, dry-run isolation and
validation-probe RC authority.

`test_verified_repair.py` uses actual Git and offline pytest for repair failure,
protected-test edits, successful repair then integration, ledger publication faults,
recovery without redispatch, structured missing-summary success, provider-free
repair/integration/no-op CLI operations, whole/step repair code 4, durable integration
repair status, blocked automatic repair retries and forged subset contracts.

R06 (whole-plan repair reported as success), R11 (integration prose ignored process
failure), A01 (SUBSLICE overwrote parent fields) and A02 (invalid/phantom plans) have
explicit regressions. Existing acceptance, collection, ownership and integration
regressions remain in the M2 full run.

## Verification record

- Initial compatibility checks identified obsolete expectations; updated to explicit
  result objects, strict plan rejection and code 5 for missing prerequisites.
- New-contract/repair selection: 41 passed (44.31s).
- Focused compatibility plus real Git: **75 passed** (297.22s), log
  `.cld/t07-verification/targeted.log`.
- Full offline M2 run: **603 passed**, three outdated test expectations failed,
  1 live evaluation deselected, no xfails, two existing deepeval warnings; 722.98s.
  `.cld/t07-verification/full-suite.log`. Two selectors now fail at plan validation
  rather than delivery; missing Git now returns gate 5. These were test-only
  corrections, not production defects.
- Early-validation follow-up: **4 passed** (4.91s),
  `.cld/t07-verification/early-validation-followup.log`.
- Final follow-up: **52 passed**, 32 deselected (4.88s), covering all three corrected
  expectations and the added selector regressions;
  `.cld/t07-verification/final-followup.log`. Together the runs verify all 609
  distinct current offline tests.
- Selector follow-up: **68 passed** (2.74s), including three additional regressions;
  `.cld/t07-verification/selector-followup.log`. This covers the only production
  change after full-run startup: stricter quoted-backslash/flag/quote validation.
- `compileall` and `git -c core.safecrlf=false diff --check` passed during development.

Windows tested; no new POSIX run claimed. No sub-agents or live provider calls;
executor usage zero and lead token counters unavailable. Commit/push the verified T07 slice, then pause for explicit token availability before T08.
