# Review defect register

Baseline: v0.2.0, commit `c3ced8a5fbbb964019352f04da8d509858644ee8`. R01 and the R02 failed-completion acceptance defect are closed by T02. R03 through R13 remain open; process interruption/timeout follow-up remains in T08 and preservation in T03. T01 closed harness observation A04. Closing evidence is linked below.

| Fixed | ID / severity | Current location | Reproduction / required regression | Owner tasks |
|---|---|---|---|---|
| [x] | R01 P1: executor commits hide forbidden changes | `engine/cld/executors/_capture.py:34` | Commit a forbidden file inside the worktree; capture currently reports no files and accepts it. Reject relative to immutable dispatch base, including changed tests. | T02 |
| [x] | R02 P1: failed dispatch accepted | `engine/cld/orchestrator.py:132` | Return `ok=False` after writing code; passing tests currently allow acceptance using an empty reported diff. Error must fail and preserve actual edits/logs. | T02, T08 |
| [ ] | R03 P1: commit failure loses accepted work | `engine/cld/orchestrator.py:390` | Reject commit via local hook or injected nonzero RC; current result is complete after worktree removal. No acceptance until commit/tree verified and durable; recovery remains. | T03 |
| [ ] | R04 P1: escalation/resume branch collision | `engine/cld/worktree.py:11` | Fail first rung, enter second; `slice-A` already exists. Verify second dispatch and restart after interruption with real Git. | T04 |
| [ ] | R05 P1: dependencies absent / failure ignored | `engine/cld/orchestrator.py:476` | A writes an interface, B depends on A; B currently starts without it. Failed/deferred A must block B. Integrated candidate must be base for B. | T06 |
| [ ] | R06 P1: repair exits zero | `skill/scripts/run_delivery.py:762` | Whole-plan result has only `needs_repair=['A']`; current exit is 0 and output omits A. Assert non-success, reason, and next action. | T07, T11 |
| [ ] | R07 P2: wheel misses provider resources | `pyproject.toml:21` | Build wheel and import `load_providers` outside checkout/editable paths. Current wheel lacks `.md` and raises FileNotFoundError. | T17 |
| [ ] | R08 P2: ledger follows caller cwd | `skill/scripts/run_delivery.py:600` | Two `--repo` values, same invocation directory and slice IDs; state must stay isolated. Restart same repo from another cwd. | T05 |
| [ ] | R09 P2: automatic validation unwired | `skill/scripts/run_delivery.py:723` | Unknown explicit/default/tag/escalated model must enter validation or return an explicit blocked policy outcome before real slice dispatch. | T09 |
| [ ] | R10 P2: no executor timeout | All provider default runners; Cursor `_timeout` unused | Sleeping child and grandchild must terminate within deadline; preserve partial files and log timeout distinctly. | T08 |
| [ ] | R11 P2: integration gate accepts errors | `engine/cld/integration_gate.py:22` | `__CLD_PYTEST_RC__=1` with `1 passed, 1 error` currently passes. Gate must use process RC and verified candidate. | T06, T07 |
| [ ] | R12 P2: retries/cost missing from usage | `engine/cld/orchestrator.py:183`, `engine/cld/usage.py:77` | Two attempts plus escalation and validation: cumulative totals survive resume, retain model attribution, cost unknown stays unknown. | T10 |
| [ ] | R13 P2: release ignores failed native commands | `sync-public.ps1:100`, `release.ps1:73` | Fake Git push/tag/commit and gh failure stop later actions; CI result must match intended SHA/workflow. No remote needed. | T18 |

**Additional findings included in this initiative**

| Fixed | ID | Required change and evidence | Owner |
|---|---|---|---|
| [ ] | A01: unsupported SUBSLICE overwrites parent fields | Reject obsolete blocks with source location; remove unsupported examples; parent data must not silently change. | T07, T20 |
| [ ] | A02: invalid DAG/plan inputs | Reject duplicate IDs, missing dependencies, empty selectors, invalid complexity, unsafe IDs/paths; no phantom endless pending layer. | T07 |
| [ ] | A03: corrupt ledger treated as fresh | Missing is new; unreadable/invalid is blocked; existing evidence must not be truncated. | T05 |
| [x] | A04: test harness duplicates old capture | Harness, concurrent and step-through executors now reuse production capture; real file/Git-tree assertions retained. [T01 evidence](T01-EVIDENCE.md). | T01 complete; T02 maintains coverage |
| [ ] | A05: platform claims exceed CI evidence | Publish explicit host/provider/OS coverage; add intended CI coverage or narrow claims. | T17, T19, T20 |
| [ ] | A06: Antigravity tokens absent | Parse only if observable from a verified fixture; otherwise label token data unavailable and correct documentation. | T10, T20 |
| [ ] | A07: evidence store concurrent writes | Atomic replace plus synchronization; distinct records survive concurrent validation; corruption surfaced. | T09 |
| [ ] | A08: skill frontmatter/install contradictions | Put frontmatter first; generated bundles must not require editable install or a source-relative driver path. | T12, T13 |
| [ ] | A09: trace overwritten between runs | Per-run artifacts plus current-run pointer; retain history and bound status reads. | T05, T10 |

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

**T02 closing evidence (2026-09-10):** [T02-EVIDENCE.md](T02-EVIDENCE.md) records the real-Git regressions, 479-pass final suite, and compatibility limits. Resolve the closing commit with `git log -1 --format=%h -- engine/cld/candidate.py`. Only R01/R02 acceptance markers were removed; six expected failures retain their T03/T04/T06 owners.
