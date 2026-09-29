# T08 execution evidence

Updated 2026-09-17. Starting commit `4dfad8c`. No live providers, sub-agents or
model calls. Executor tokens: zero. Lead token counters: unavailable.

**Complete:** [T08-CONTRACT.md](T08-CONTRACT.md). R10 and the R02 process follow-up
close. Code/test head `53cc2c0` is pushed; closing documentation is identified by
commit subject `docs: close T08 and hand off T09`. Both final CI jobs passed.

Windows Python 3.13 local runs:

- Provider/process/CLI/validation focused suite: **106 passed**, 26.60s.
- Provider wiring/recovery/T07 contracts: **58 passed**, 15.19s.
- Final lifecycle suite including parallel cancellation: **32 passed**, 24.85s.
- Provider log/transcript follow-up: **27 passed**, 20.76s.
- Cleanup-failure/isolated-bootstrap follow-up: **34 passed**, 28.39s.
- Full offline suite: **641 passed**, 1 live eval deselected, 2 existing deepeval warnings, 756.36s.
- Final cleanup-bound follow-up: **36 passed**, 27.18s; **645 distinct current tests verified across local runs**.

Logs under ignored `.cld/t08-verification/`: targeted.log, followup.log,
lifecycle.log, full-suite.log, final-followup.log, cleanup-followup.log,
bounds-followup.log, concurrency-followup.log and platform CI logs.
The lifecycle tests execute real synthetic Python processes: stdin EOF, long UTF-8
input, invalid output bytes, environment additions, nonzero after file writes,
missing/access-denied executable, ordinary and authentication failures, timeout,
cooperative cancellation, KeyboardInterrupt and normal parent exit with a live
child. Windows assignment failure confirms that no uncontained target starts.
Recovery tests assert retained edits, reachable recovery refs, both stream paths,
no acceptance and no cancellation retry. A later parallel worker's interruption
must stop an earlier running worker, guarding against ordered-future waits.

WSL is not installed locally. The Ubuntu/Windows CI matrix now also runs on pushes
to `refactor/codex-support`. [Final CI run](https://github.com/jhesham/cross-llm-delivery/actions/runs/35190206051)
checks code/test commit `53cc2c0` with Python 3.11:

- Ubuntu: **642 passed, three Windows-only skips**; all generator smoke builds pass.
- Windows: **645 passed, no skips**; all generator smoke builds pass.

Counts are taken from pytest's progress records (CI uses double-quiet output).
One live evaluation is excluded by the repository's default marker policy.
Antigravity log/transcript retention and cleanup-failure handling were refined
after local full-suite startup; local follow-ups cover those changes and remote
CI checks the final committed source. POSIX lifecycle tests execute in Ubuntu;
the Windows-only tests cover Job assignment, accounting errors and cleanup bounds.

The first Windows CI run on `fc8a3be` had one failure in the pre-existing parallel
fixture: a 20ms sleep did not guarantee overlap on a loaded runner. All other
Windows tests passed, including the new process contracts. The concurrency test
now uses a three-party barrier with a bounded wait, preserving the actual overlap
assertion. Local follow-up: **18 passed**, 1.14s. No test was weakened or skipped to
hide that failure. Superseded CI runs were cancelled while awaiting final-head CI.
