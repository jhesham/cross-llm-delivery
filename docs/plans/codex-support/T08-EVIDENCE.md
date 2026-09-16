# T08 execution evidence

Updated 2026-09-17. Starting commit `4dfad8c`. No live providers, sub-agents or
model calls. Executor tokens: zero. Lead token counters: unavailable.

Implementation: [T08-CONTRACT.md](T08-CONTRACT.md). Verification in progress;
do not treat this initial evidence checkpoint as the T08 completion gate.

Windows Python 3.13 local runs:

- Provider/process/CLI/validation focused suite: **106 passed**, 26.60s.
- Provider wiring/recovery/T07 contracts: **58 passed**, 15.19s.
- Final lifecycle suite including parallel cancellation: **32 passed**, 24.85s.
- Full offline suite running; one live evaluation remains excluded by default.

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
on pushes to `refactor/codex-support`; remote results are pending. No POSIX execution
claim until that run is inspected. Antigravity log/transcript retention was refined
after local full-suite startup and requires a final focused follow-up.
