# F01 — red pytest output can be misclassified as provider authentication

Observed while integrating N06, 2026-10-03. **Implemented 2026-10-04;
exact-source CI pending.** See [F01 implementation evidence](F01-PYTEST-DIAGNOSTICS-FIX.md).
The original diagnosis and receipts below remain historical evidence.
This is a false rejection of valid assertion-red integration preflight, not
evidence of false approval or an actual provider authentication failure.

`run_process` applies `exit_error(returncode, output)` to every subprocess.
`cli.pytest_test_runner` preserves an `authentication` error label, while
`CandidateVerifier.preflight` correctly refuses a test run carrying a process
error. A verbose pytest item name can therefore trigger the provider-text
heuristic when another selected test fails.

Concrete receipt, retained locally:
`.cld/runs/7de01c823cb64fb1a1151de8fbb9f89c/integration/f1c11ca65b834ee9bc35c12b2d14c91e/`.
The committed N06 baseline had **29 intended assertion failures, 203 passes**,
but `baseline.txt.json` recorded `error: authentication`. Its output included a
passing item named
`tests/test_process.py::test_observable_authentication[authentication failed-authentication]`.
No provider call was part of that integration transaction.

N06 integration was completed through the unchanged frozen N06 acceptance suite
after checked ledger reconciliation; the full adjacent group then passed all
232 cases on integrated source. The failed transaction and backup remain intact.
This contains the operational impact for N06 without changing diagnostic policy.

## Completed F01 slice

- [x] Commit a local subprocess regression: pytest prints a passing item with an
      authentication-like parameter label and an unrelated assertion fails.
      `CandidateVerifier.preflight` must recognize valid assertion-red output.
- [x] Separate lifecycle/launch errors from provider-output heuristics for the
      pytest adapter. Consider an explicit process classification option or
      narrowly handling documented pytest exits; do not globally disable genuine
      provider authentication diagnostics.
- [x] Keep collection/configuration failures, missing return codes, cancelled
      tests and timeouts fail-closed. Test actual provider authentication output
      still receives its final error and cannot trigger retries/escalation.
- [x] Re-run the original broad frozen integration baseline and final suite.
- [x] Regenerate affected bundles from committed source and record CI/handoff.

F01's 30 frozen cases pass. The original broad historical baseline now retains
29 intended failures and 203 passes with no process error, and independent
preflight accepts it as assertion-red. The same selector passes all 232 cases
on final source. Genuine provider authentication remains final. Generation source:
`6170865`; pushed source/artifacts `6037bb1`,
[exact-source CI run 37142332565](https://github.com/jhesham/cross-llm-delivery/actions/runs/37142332565)
in progress at the stopping checkpoint. Require all four jobs green before promotion.

Do not change frozen selectors silently or relabel saved evidence. The earlier
precise-selector workaround is no longer required for this diagnostic defect;
changes to a bound acceptance contract still require checked reconciliation.
