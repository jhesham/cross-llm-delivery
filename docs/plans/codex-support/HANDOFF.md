# Current handoff

Updated 2026-09-17. **T01 through T08, M1 and M2 complete. Paused before T09.** Read
[T08-CONTRACT.md](T08-CONTRACT.md) and [T08-EVIDENCE.md](T08-EVIDENCE.md).
Do not start T09 without explicit token-availability confirmation. T08 code and
tests are committed/pushed; resolve the closing docs commit with
`git log -1 --format=%h --grep="^docs: close T08"` and verify its remote push.
Code/test head `53cc2c0` is pushed to `public/refactor/codex-support`. Final CI:
https://github.com/jhesham/cross-llm-delivery/actions/runs/35190206051
Final CI: **Windows 645 passed; Ubuntu 642 passed, three Windows-only skips**.
Both platforms pass generator smoke builds. Local Python 3.13 full suite: 641
passed, one live eval excluded, two existing warnings; follow-ups cover 645 distinct
current tests. The previous Windows run exposed an older
20ms concurrency-fixture assumption, now replaced by a bounded barrier (18 local
follow-up passes). No implementation failures were found in that run.

T08 adds dispatch/probe deadlines (600s/30s; CLD_DISPATCH_TIMEOUT and
CLD_PROBE_TIMEOUT), process-tree cancellation, bounded cleanup confirmation,
separate retained stream artifacts and error classification. Windows uses Jobs;
POSIX uses process groups. Cancellation prevents retry/escalation; cleanup that
cannot be confirmed aborts without inspecting the candidate. Provider invocation
and approval flags remain. CLI/validation pytest uses the same containment.
The detailed contract describes scope limits and the legacy injected runner API.

Next after token confirmation is T09 (8–14k): read phase 3,
validate.py, evidence.py, models.py, providers_api.py, CLI provider resolution and
the T07/T08 contracts. Implement consistent model validation, durable evidence,
noninteractive spend admission and selected-provider preflight. No live services.
No sub-agents/live providers; executor usage zero; lead counters unavailable.
If explicitly requested, sub-agents use gpt-5.6-luna at max. Kimi K3 via OpenCode
remains gated through T09; verify its exact model ID before any live dispatch.
Schema 2 and T06/T07 acceptance/integration gates remain. Generated plugin copies
refresh in T12/T17. This is a refactoring checkpoint, not a release or merge.
