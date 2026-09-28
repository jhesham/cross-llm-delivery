# Current handoff

Updated 2026-09-28. **T01–T17, M1–M4 and optional M6 complete. T18 in progress:
implementation and 55 focused local regressions pass; exact pushed-SHA four-job
CI and clean-checkout previews pending. Do not start T19.** Branch
`refactor/codex-support`, remote `public`. No main merge/release/tag/public mirror
or global skill installation has been authorized by this task.

Read [T18 evidence](T18-EVIDENCE.md), [tracker](TRACKER.md), and only
[T18 requirements](06-PACKAGING-RELEASE.md#t18--checked-release-automation).
The red contract/acceptance baseline is `eef006b`. Checked Python release
operations and PowerShell forwarding wrappers replace unchecked native scripts;
bundle mirror publishing uses explicit refs, atomic push and exact expected-SHA
leases. Source versions and both generated plugin sets are checked. All 55
focused Windows Python 3.13 release/publish checks pass, including concurrent
remote updates, failure retention, literal notes, wrapper exit codes and
read-only previews. Wait for full Windows/Ubuntu Python 3.11/3.14 CI plus all
bundle/plugin/catalog steps, then close R13/T18 and commit the closure evidence.

Exact Kimi K3/OpenCode dogfood run `901f496d00b54ceea68595cb6c6a6b88` validated
but timed out after 600 seconds with no changes/candidate. Validation reported
60,535 provider tokens/USD 0.059661; production usage/cost unknown. Attempts
exhausted after validation + production; no further provider call or substitute.
Ledger `.cld/t18/ledger.json`; worktree and process metadata paths are in evidence.
Lead usage unavailable; original 8–12k lead estimate exceeded. After T18 closure,
stop for explicit user token confirmation before T19 migration/interruption
rehearsal. T20 documentation/candidate follows T19. M5 remains open.

Previous proof is linked from [T14](T14-EVIDENCE.md), [T16](T16-EVIDENCE.md), and
[T17C](T17C-EVIDENCE.md). Codex/Claude host discovery and Windows Codex executor
canary passed; macOS, live POSIX providers and live process interruption remain
unverified. Preserve exact model IDs, generated-file policy and one-slice
checkpoints. Do not repeat broad paid calls to rediscover existing proof.
