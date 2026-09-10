# Current handoff

Updated: 2026-09-11. Initiative: Codex support and review remediation.

**State:** T01 through T04 and M1 complete; paused before T05 pending explicit
confirmation of token availability. Branch `refactor/codex-support`, remote `public` on GitHub.
T04 starts from `24b8d85`; resolve its closing commit with
`git log -1 --format=%h --grep='^fix: T04 '`. Verify commit/push before final pause.

**Mandatory checkpoint:** Verify and commit each slice with progress updates, then
wait for explicit confirmation of token availability before starting another.
T05 has not started. The user's push authorization remains in effect for these
refactoring branch checkpoints; this is not a release or merge.

**Next after confirmation:** [T05: build identity and ledger migration](02-STATE-ORCHESTRATION.md#t05--build-identity-and-ledger-migration).
Estimate 12–18k lead tokens. Read that contract, `ledger.py`, `attempts.py`,
`recovery.py`, and CLI ledger loading. Add a build-wide writer lock, versioned build
identity, corruption handling and explicit backed-up migration. Preserve actual
accepted/recovery refs and all old candidates. The T04 per-slice lock does not
serialize different slices writing one legacy ledger from separate processes.

**T04 evidence:** [T04-EVIDENCE.md](T04-EVIDENCE.md). Focused existing tests:
71 passed, 2 strict xfailed; post-fix Git/ownership checks: 15 passed, path checks:
4 passed. Final M1 suite: **513 passed, 2 strict xfailed, 1 deselected, 2 existing
warnings**, 454.60 seconds. Log: `.cld/t04-verification/full-suite-final.log`.
The initial full run found a Windows parent-creation/path-resolution race, now fixed. R04's escalation xfail was removed;
only the two T06 dependency regressions remain expected failures.

**Implemented boundary:** [A04](ARCHITECTURE.md) records unique run/session refs,
pre-creation reservation journals, OS-held slice ownership, safe configured roots,
bounded recovery context and legacy compatibility. Within-session retries reuse
the prior candidate; escalation/restart use a fresh base with preserved paths/refs.
Hard process exit releases ownership without deleting lock files or old branches.
Collected journal reconciliation still avoids redispatch. Default worktree root is
`<repo>/.cld/worktrees`; `--worktree-root` is absolute or relative to `--repo`.
Test temporary directories still use normal Python/Git temp locations.

**Migration:** Schema-1 journals add `run_id`, `branch`, `worktree_root`, `owner_pid`,
`retry_policy` and `previous`. The ledger retains `commit`, `collection`,
`recovery_path`, `worktree_path`. Legacy `slice-<id>` refs are read-only input;
legacy collected worktrees require manual cleanup. No automatic branch deletion.

**Verification commands:**

```text
python -m pytest tests/integration/test_attempt_resume.py -o addopts="" -q --tb=short
python -m pytest -o addopts="-m 'not eval'" -q --tb=short
```

Committed plugin copies remain unchanged for T12/T17. Existing protected acceptance
and explicit simulation rules remain. Windows execution only; no new POSIX run.

**Dogfooding/usage:** No sub-agents or provider calls in T04; executor usage zero,
lead counters unavailable. User preference: any Codex sub-agents must use
`gpt-5.6-luna` with `max` reasoning and bounded briefs. Kimi K3 via OpenCode remains
the later cross-LLM executor; resolve its exact model ID before live dispatch,
without substitution. Bootstrap through T09 before live dogfooding.
