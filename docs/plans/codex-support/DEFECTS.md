# Review defect register

Baseline: v0.2.0, commit `c3ced8a5fbbb964019352f04da8d509858644ee8`. R01 through R04 are closed by T02/T03/T04; T08 closes the R02 interruption/timeout follow-up and R10. R08 is closed by T05; R05 is closed by T06; R06/R11 are closed by T07; T09 closes R09 and A07; T10 closes R12 and A06; T17A closes R07, and T17C closes A05. R13 remains open. T01 closed harness observation A04. Closing evidence is linked below.

| Fixed | ID / severity | Current location | Reproduction / required regression | Owner tasks |
|---|---|---|---|---|
| [x] | R01 P1: executor commits hide forbidden changes | `engine/cld/executors/_capture.py:34` | Commit a forbidden file inside the worktree; capture currently reports no files and accepts it. Reject relative to immutable dispatch base, including changed tests. | T02 |
| [x] | R02 P1: failed dispatch accepted | `engine/cld/orchestrator.py:132` | Return `ok=False` after writing code; passing tests currently allow acceptance using an empty reported diff. Error must fail and preserve actual edits/logs. | T02, T08 |
| [x] | R03 P1: commit failure loses accepted work | `engine/cld/recovery.py`, `engine/cld/orchestrator.py` | Reject commit via local hook or injected nonzero RC; current result is complete after worktree removal. No acceptance until commit/tree verified and durable; recovery remains. | T03 |
| [x] | R04 P1: escalation/resume branch collision | `engine/cld/worktree.py:11` | Fail first rung, enter second; `slice-A` already exists. Verify second dispatch and restart after interruption with real Git. | T04 |
| [x] | R05 P1: dependencies absent / failure ignored | `engine/cld/orchestrator.py:476` | A writes an interface, B depends on A; B currently starts without it. Failed/deferred A must block B. Integrated candidate must be base for B. | T06 |
| [x] | R06 P1: repair exits zero | `skill/scripts/run_delivery.py:762` | Whole-plan result has only `needs_repair=['A']`; current exit is 0 and output omits A. Assert non-success, reason, and next action. | T07, T11 |
| [x] | R07 P2: wheel misses provider resources | `pyproject.toml:21` | Wheel and sdist now include all six provider Markdown files; installed wheel loads three providers and CLI help under `python -I -S` outside checkout. [T17A evidence](T17A-EVIDENCE.md). | T17A |
| [x] | R08 P2: ledger follows caller cwd | `skill/scripts/run_delivery.py:600` | Two `--repo` values, same invocation directory and slice IDs; state must stay isolated. Restart same repo from another cwd. | T05 |
| [x] | R09 P2: automatic validation unwired | `skill/scripts/run_delivery.py:723` | Unknown explicit/default/tag/escalated model must enter validation or return an explicit blocked policy outcome before real slice dispatch. | T09 |
| [x] | R10 P2: no executor timeout | `engine/cld/process.py`, provider default runners | Sleeping child and grandchild terminate within deadline; partial files and both streams survive; cleanup failure aborts without candidate inspection. [Evidence](T08-EVIDENCE.md). | T08 |
| [x] | R11 P2: integration gate accepts errors | `engine/cld/integration_gate.py:22` | `__CLD_PYTEST_RC__=1` with `1 passed, 1 error` currently passes. Gate must use process RC and verified candidate. | T06, T07 |
| [x] | R12 P2: retries/cost missing from usage | `engine/cld/orchestrator.py:183`, `engine/cld/usage.py:77` | Two attempts plus escalation and validation: cumulative totals survive resume, retain model attribution, cost unknown stays unknown. | T10 |
| [ ] | R13 P2: release ignores failed native commands | `sync-public.ps1:100`, `release.ps1:73` | Fake Git push/tag/commit and gh failure stop later actions; CI result must match intended SHA/workflow. No remote needed. | T18 |

**Additional findings included in this initiative**

| Fixed | ID | Required change and evidence | Owner |
|---|---|---|---|
| [x] | A01: unsupported SUBSLICE overwrites parent fields | Reject obsolete blocks with source location; remove unsupported examples; parent data must not silently change. | T07, T20 |
| [x] | A02: invalid DAG/plan inputs | Reject duplicate IDs, missing dependencies, empty selectors, invalid complexity, unsafe IDs/paths; no phantom endless pending layer. | T07 |
| [x] | A03: corrupt ledger treated as fresh | Missing is new; unreadable/invalid is blocked; existing evidence must not be truncated. | T05 |
| [x] | A04: test harness duplicates old capture | Harness, concurrent and step-through executors now reuse production capture; real file/Git-tree assertions retained. [T01 evidence](T01-EVIDENCE.md). | T01 complete; T02 maintains coverage |
| [x] | A05: platform claims exceed CI evidence | Offline CI now covers Python 3.11/3.14 × Windows/Ubuntu, with six bundles and plugin gates; README/INSTALL/KNOWN-ISSUES distinguish historical Windows live calls, offline Ubuntu tests, and unverified macOS/POSIX live dispatch. [T17C evidence](T17C-EVIDENCE.md). T14/T19 may add new evidence. | T17C |
| [x] | A06: Antigravity tokens absent | Parse only if observable from a verified fixture; otherwise label token data unavailable and correct documentation. | T10, T20 |
| [x] | A07: evidence store concurrent writes | Atomic replace plus synchronization; distinct records survive concurrent validation; corruption surfaced. | T09 |
| [ ] | A08: skill frontmatter/install contradictions | Put frontmatter first; generated bundles must not require editable install or a source-relative driver path. | T12, T13 |
| [x] | A09: trace overwritten between runs | T05 preserves per-run artifacts/current pointer and history. Bounded status indexing remains a T10 follow-up. | T05 complete; T10 follow-up |

**Closing evidence template**

```text
Rxx / Axx:
Regression test:
Failing-baseline behavior:
Passing result / environment:
Commit:
Residual limitation:
```

Original local review and probe files remain under `D:\claude_server\cld-review-artifacts` if useful on this machine. The task regressions must work without those absolute paths, archived wheels, or temporary repositories. Recreate minimal fixtures from the conditions above; do not commit private build transcripts or local configuration.

**T02 closing evidence (2026-09-10):** [T02-EVIDENCE.md](T02-EVIDENCE.md) records the real-Git regressions, 479-pass final suite, and compatibility limits. Closing commit: `a6b1b68`. Only R01/R02 acceptance markers were removed; six expected failures retain their T03/T04/T06 owners.

**T03 closing evidence (2026-09-10):** [T03-EVIDENCE.md](T03-EVIDENCE.md) records rejecting-hook, judge-exception, disk/Git/save and recovery regressions. Final suite: 501 passed, 3 xfailed, 1 deselected. Resolve the closing commit with `git log -1 --format=%h --grep='^fix: T03 '`. The three remaining expected failures belong to T04/T06.

**T04 closing evidence (2026-09-11):** [T04-EVIDENCE.md](T04-EVIDENCE.md) records unique attempts, actual two-rung dispatch, hard-stop restart, active ownership, orphan/legacy preservation and configured-root checks. Final M1 suite: 513 passed, 2 xfailed, 1 deselected. Resolve the closing commit with `git log -1 --format=%h --grep='^fix: T04 '`. Only the two T06 dependency regressions remain expected failures.

**T05 closing evidence (2026-09-11):** [T05-EVIDENCE.md](T05-EVIDENCE.md) and [migration guide](T05-MIGRATION.md) close R08, A03 and A09 trace preservation. Full run: 531 passed and one stale fixture corrected; follow-up: 41 passed, covering 532 distinct tests overall. Two T06 xfails remain. T10 still owns bounded status reads. Closing subject starts `fix: T05`.

**T06 closing evidence (2026-09-15):** [T06-EVIDENCE.md](T06-EVIDENCE.md) closes R05 with actual Git/pytest dependency visibility and blocking, isolated integration and interruption recovery. Full suite: 555 passed, no xfails, 1 deselected; final guard follow-up: 3 passed, 556 distinct verified tests. R11 remains open for T07's structured runner/legacy integration-gate protocol; the new production integration path already enforces authoritative RC. Closing subject starts `fix: T06`.

**T07/M2 closing evidence (2026-09-17):** [T07-EVIDENCE.md](T07-EVIDENCE.md) and [contract](T07-CONTRACT.md) close R06/R11/A01/A02. Full run: 603 passed; three outdated test expectations were corrected and verified in the 52-pass final follow-up. Selector follow-up: 68 passed. 609 distinct passing tests verified overall; no xfails, one live evaluation excluded. Generated host copies and versioned JSON remain T11/T12/T17 work. Closing subject starts `fix: T07`.

**T09 closing evidence (2026-09-18):** [T09-EVIDENCE.md](T09-EVIDENCE.md) and [contract](T09-CONTRACT.md) close R09 and evidence-store concurrency A07. Defaults/tags/unknown IDs/escalation cannot bypass admission; failed/forced/expired/context-changed evidence, noninteractive policy blocks and concurrent atomic writes have offline regressions. Windows CI 685 passed; Ubuntu 682 passed/3 Windows-only skips. Code/test head `3caf863`. Architecture decision A07 (full CLI JSON) remains T11 work.

**T10/M3 closing evidence (2026-09-23):** [T10-EVIDENCE.md](T10-EVIDENCE.md) and [contract](T10-CONTRACT.md) close R12/A06. Per-attempt journals retain failed/retried/escalated/validation usage and cost provenance; shared reservations prevent concurrent budget oversubscription. Interrupted unknown usage is not free. Ledger/status totals agree. Antigravity usage is explicitly unavailable; no unsupported parser or zero-cost claim. Final CI: Windows 709 passed; Ubuntu 706 passed/3 Windows-only skips; both generator smoke checks passed. Code/test head `8f3c5db`. A09 artifact/recovery preservation remains covered.
