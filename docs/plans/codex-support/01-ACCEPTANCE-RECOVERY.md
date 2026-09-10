# Phase 1 — Acceptance and recovery

Outcome: the engine can be trusted to retain and verify candidate code. No live dogfooding of engine repair before this phase passes. Work directly with local deterministic tests. Relevant architecture: A02–A04.

## T01 — Baseline and regression harness

Dependencies: none. Estimate: 6–10k lead tokens. Start with `tests/integration/harness.py`, `_capture.py`, `worktree.py`, and the acceptance branches in `orchestrator.py`. Scope: test infrastructure and small portable regression fixtures.

- [x] Record current HEAD, Python/Git versions, selected test count, and a clean baseline test result. Preserve unrelated user edits.
- [x] Replace or adapt duplicated harness capture so providers and integration tests use the production helper; keep outcome assertions independent by inspecting Git objects/files.
- [x] Add minimal real-Git regressions for executor commits, nonzero dispatch after writes, rejecting commit hooks, escalation collision, and dependent code visibility.
- [x] Add fault injection for judge, ledger-save, diff-capture, and cleanup failure. All test repositories stay in test-owned directories; no global Git settings or paid CLIs.
- [x] Document which new cases intentionally fail on baseline and which task closes each. If retained as strict temporary xfails, include defect IDs; never allow unexpected passes or ship with those xfails still masking defects.

**Gate:** Existing selected tests still pass; each new failure demonstrates a review defect and is reproducible offline. Handoff lists the exact targeted pytest commands. Run `python -m pytest tests/integration -q` plus the baseline suite once, saving bounded summaries.

Completed 2026-09-10. [Evidence and closure owners](T01-EVIDENCE.md): baseline 419 passed; final suite 421 passed / 9 strict expected failures / 1 deselected. Unmasked regressions: 9 intended contract failures and 2 passing fault controls. Production defects remain open for their owning tasks.

## T02 — Independent candidate verification

Dependencies: T01. Estimate: 12–18k; split candidate capture and frozen judging if needed. Files: `engine/cld/executors/_capture.py`, `executors/base.py`, `orchestrator.py`, `judge.py`, corresponding provider boundaries/tests. Suggested new module: `engine/cld/candidate.py`.

- [x] Introduce immutable dispatch base and candidate metadata, captured before the executor can change HEAD. Extend injected contracts explicitly instead of catching arbitrary TypeError as a signature fallback.
- [x] Capture the complete tree difference against that base, with NUL-delimited names and checked Git RCs; cover staged/untracked/binary/rename/delete/mode changes and committed changes.
- [x] Reject `ok=False`, malformed completion, interrupted capture, and forbidden paths before acceptance. Independently inspect the filesystem/Git state rather than trust `ExecutorResult.files_changed`.
- [x] Protect committed acceptance inputs and disallow path escape. Check baseline tests exist; distinguish expected assertion failure from collection/configuration failure.
- [x] Judge a frozen candidate with trusted acceptance inputs. Detect test-time source changes, include candidate/test fingerprints, and reject any collection that differs from the verified tree.
- [x] Cover executor-committed test tampering, filenames with spaces/Unicode/newlines where the OS permits, symlink/path behavior, and executor report spoofing. Preserve no-change success only under an explicit valid already-satisfied policy.

**Gate:** R01/R02 regressions pass with real Git. Forbidden edits cannot be accepted by committing them, returning an empty report, failing dispatch, or mutating files during tests. Run capture/judge/delivery/integration tests; inspect API compatibility with all three providers.

Completed 2026-09-10. [Evidence and compatibility notes](T02-EVIDENCE.md): 479 passed, 6 strict expected failures, 1 live evaluation deselected. R01 and R02 acceptance regressions pass without xfail. Commit/recovery defects remain assigned to T03; T03 requires the next user token checkpoint.

## T03 — Checked collection and preservation

Dependencies: T02. Estimate: 10–16k. Files: `orchestrator.py`, `worktree.py`, candidate module, ledger persistence boundary, recovery tests.

- [x] Make collection return a verified commit/tree or a structured error. Check every staging/commit/reachability operation; support a valid no-op without inventing a commit failure.
- [x] Persist exactly the verified candidate; avoid blanket staging of post-judge files. Ensure accepted commits stay reachable through durable refs.
- [x] Record commit/tree/attempt outcome durably before any success report or cleanup. Simulate ledger-save failure after commit and recovery on restart.
- [x] Preserve candidate patches including binary/new files and executor commits relative to the original base, plus raw dispatch/judge diagnostics per attempt.
- [x] Preserve on every exceptional path. If writing/validating the recovery artifact fails, retain the worktree and report its path; never swallow loss of the only copy.
- [x] Add rejecting commit hook, failed add, disk/save error, judge exception, and cleanup error regressions. Verify original user checkout unchanged.

**Gate:** R03 passes: collection failure yields no accepted/DONE result and implementation remains recoverable. Recovery artifacts reconstruct the candidate; a successful path records the exact tested tree. Run collection/preservation and delivery suites.

Completed 2026-09-10. [Evidence and recovery instructions](T03-EVIDENCE.md): 501 passed, 3 strict expected failures, 1 live evaluation deselected. R03 regressions pass without xfail. Retained failed worktrees and existing slice branch collisions are deliberately left for T04.

## T04 — Resumable attempts and worktrees

Dependencies: T03. Estimate: 10–16k. Files: `worktree.py`, `orchestrator.py`, attempt metadata/ledger, recovery fixtures.

- [ ] Introduce run/slice/attempt-specific refs and configurable worktree roots; canonicalize and verify boundaries before create/remove operations.
- [ ] Support escalation without branch collision; record the chosen fresh-base or prior-candidate retry policy. Pass bounded diagnostics and preserved-candidate paths to the next attempt.
- [ ] Recover interrupted attempts from recorded refs/worktrees; distinguish an active owner from stale state. Never reset an accepted or unrelated branch.
- [ ] Reserve unique attempt IDs under synchronization; avoid duplicate worktree creation in concurrent or restarted runs.
- [ ] Preserve compatibility by reading old `slice-<id>` refs rather than assuming they can be removed. Document migration handoff for T05.
- [ ] Test fail→retry→pass, fail→escalate→pass, stop→restart, orphaned worktree/ref, two independent slices, and configured writable root inside a restricted workspace.

**Gate:** R04 passes with actual Git. Both rungs really dispatch and interrupted work can resume without branch deletion. Run the full offline suite at **M1**; record any intentional migrations before beginning T05.
