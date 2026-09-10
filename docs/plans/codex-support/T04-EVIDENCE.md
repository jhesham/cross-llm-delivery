# T04 evidence — resumable attempts and worktrees

Starting commit: `24b8d850d3d2f80ac14daa129ed936c2e394d2b9` on
`refactor/codex-support`. Date: 2026-09-11. Closing commit can be resolved with
`git log -1 --format=%h --grep='^fix: T04 '`.

## Implemented contract

- Unique invocation/session branch and worktree identities; journal reservation
  precedes Git creation. Every in-session retry keeps separate snapshot refs/logs.
- CLI/API configurable worktree root, canonical boundary checks, branch/repository
  verification before cleanup, and preservation when cleanup ownership changes.
- Explicit prior-candidate in-session retries and fresh-base escalation/restart.
  Previous diagnostics and recovery locations are passed as bounded context.
- OS-held slice locks reject competing owners without altering their ledger.
  Process death releases ownership; no age/PID guesses or lock-file deletion.
- Restart preserves old worktrees/refs, tolerates orphaned artifacts, and reads legacy
  slice branches without reset/deletion. T03 collected-outcome reconciliation remains.
- CLI dependency warnings now use recorded accepted commits, with legacy fallback.
  Actual dependency integration and failure blocking remain T06.

## Verification

- Focused existing delivery/worktree/collection/CLI checks: **71 passed, 2 strict
  xfailed** in 216.68 seconds. The R04 escalation marker was removed; both rungs
  really dispatch with actual Git.
- Initial new T04 regression run: **8 passed** in 58.32 seconds. Two additional
  reservation/cleanup ownership cases are included in the full suite.
- First full run: 511 passed, 1 failed, 2 xfailed, 1 deselected in 443.09 seconds.
  The saved failure journal identified a Windows canonical-path race while another
  worker created a shared parent directory. Parent creation now finishes before
  missing-leaf resolution. Original log: `.cld/t04-verification/full-suite.log`.
- Post-fix Git/ownership checks: **15 passed** in 99.92 seconds. Path checks:
  **4 passed** in 0.22 seconds, including 80 concurrent reservations across 20 roots.
- Final full M1 offline suite: **513 passed, 2 strict xfailed, 1 live evaluation
  deselected, 2 existing deepeval warnings**, in 454.60 seconds. Log:
  `.cld/t04-verification/full-suite-final.log`. M1 and R04 pass.

```text
python -m pytest tests/integration/test_attempt_resume.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

New real-Git cases cover fail/escalate/pass with distinct paths and feedback;
hard process exit then restart; orphaned ref or worktree; legacy branch preservation;
a configured root with a runner restricting worktree mutations to that workspace
location; same-process and cross-process ownership; reservation before failed Git
creation; and cleanup after a worktree is assigned to an unrelated branch.
Existing tests cover fail/retry/pass, independent concurrent slices, and collection
interruption without redispatch. The root test constrains worktree mutations, not
all subprocess/temp writes, and is not a Codex sandbox end-to-end test.

## T05 migration handoff and limits

See [A04](ARCHITECTURE.md) for the additive schema-1 journal fields and policies.
Legacy journal/accepted/recovery refs remain readable. T05 owns full build identity,
ledger corruption handling/versioning and a build-wide writer lock. Per-slice
ownership alone does not serialize separate processes writing different slices to
one legacy ledger. T06 still owns both remaining expected dependency failures.
Committed plugin copies remain unchanged until T12/T17; generated source bundles
are checked by the suite. No release or merge is included.

No sub-agents or live provider calls were used. Executor usage: zero. Lead token
counters are unavailable; the T04 planning range was 10–16k, not measured usage.
There is insufficient usage evidence to recalibrate the remaining task estimates
at M1. The session guide records the user's `gpt-5.6-luna` with `max` preference for
any future Codex sub-agents; Kimi K3 via OpenCode remains the selected later
cross-LLM dogfooding route, gated through T09.
