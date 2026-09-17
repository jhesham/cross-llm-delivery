# T08 execution evidence

Updated 2026-09-17. Starting commit `4dfad8c`. No live providers, sub-agents or
model calls. Executor tokens: zero. Lead token counters: unavailable.

Implementation: [T08-CONTRACT.md](T08-CONTRACT.md). Verification in progress;
do not treat this initial evidence checkpoint as the T08 completion gate.

Windows Python 3.13 local runs:

- Provider/process/CLI/validation focused suite: **106 passed**, 26.60s.
- Provider wiring/recovery/T07 contracts: **58 passed**, 15.19s.
- Final lifecycle suite including parallel cancellation: **32 passed**, 24.85s.
- Provider log/transcript follow-up: **27 passed**, 20.76s.
- Cleanup-failure/isolated-bootstrap follow-up: **34 passed**, 28.39s.
- Full offline suite: **641 passed**, 1 live eval deselected, 2 existing deepeval warnings, 756.36s.
- Final cleanup-bound follow-up: **36 passed**, 27.18s; **645 distinct current tests verified across local runs**.

Logs: `.cld/t08-verification/{targeted,followup,lifecycle,full-suite}.log` (ignored).
The lifecycle tests execute real synthetic Python processes: stdin EOF, long UTF-8
input, invalid output bytes, environment additions, nonzero after file writes,
missing/access-denied executable, ordinary and authentication failures, timeout,
cooperative cancellation, KeyboardInterrupt and normal parent exit with a live
child. Windows assignment failure confirms that no uncontained target starts.
Recovery tests assert retained edits, reachable recovery refs, both stream paths,
no acceptance and no cancellation retry. A later parallel worker's interruption
must stop an earlier running worker, guarding against ordered-future waits.

WSL is not installed locally. The existing Ubuntu/Windows CI matrix now also runs
on pushes to `refactor/codex-support`; Ubuntu passed on `fc8a3be` (641 passed, two Windows-only skips); Windows CI is pending. POSIX lifecycle tests executed successfully in that Ubuntu job. Antigravity log/transcript retention and explicit
cleanup-failure handling were refined after local full-suite startup; the focused
follow-ups above cover those changes. Remote CI checks the committed source.

The first Windows CI run on `fc8a3be` had one failure in the pre-existing parallel
fixture: a 20ms sleep did not guarantee overlap on a loaded runner. All other
Windows tests passed, including the new process contracts. The concurrency test
now uses a three-party barrier with a bounded wait, preserving the actual overlap
assertion. Local follow-up: **18 passed**, 1.14s. Latest-head CI remains pending.
