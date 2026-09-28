# Current handoff

Updated 2026-09-28. **T01–T18, M1–M4 and optional M6 complete. T19 migration/
interruption rehearsal is next; stop for explicit user token confirmation.**
Branch `refactor/codex-support`, remote `public`. R13 is closed by T18. The T18
closing push must pass exact-SHA four-job CI before handing off; verify its
checks and `.cld/t18/ci-final-jobs.json`. No main merge/sync, tag, release,
provider-mirror publication or global skill copy has been executed.

Read [T18 evidence](T18-EVIDENCE.md), [preview](T18-PREVIEW.md), [tracker](TRACKER.md),
then only [T19 requirements](06-PACKAGING-RELEASE.md#t19--migration-and-interruption-rehearsal).
Red baseline `eef006b`; core source/test `032cc26` passed
[Windows/Ubuntu Python 3.11/3.14 full CI and artifact gates](https://github.com/jhesham/cross-llm-delivery/actions/runs/36392139614).
The closing commit adds the relative local-remote repair, its real-Git test,
unchanged-mirror/fetch/multiple-URL checks and final progress/preview evidence.
All 59 focused local checks pass. Checked native commands, complete matching
host manifest sets, owned recovery worktrees, literal notes, exact-SHA CI and
explicit atomic expected-SHA publishing replace unchecked scripts. Previews
changed no local refs/tracked files; full JSON/hash maps are in `.cld/t18/previews/`.

Exact Kimi K3/OpenCode run `901f496d00b54ceea68595cb6c6a6b88` validated but timed
out after 600 seconds with no changes or accepted candidate. Validation reported
60,535 provider tokens/USD 0.059661; production usage/cost unknown. Two admitted
attempts including validation exhausted its budget; no extra call or substitute.
The lead finished directly. Ledger `.cld/t18/ledger.json`; retained worktree and
process paths are in evidence. Lead usage unavailable; original 8–12k estimate
exceeded. Use smaller, bounded dogfood contracts for T19/T20; avoid repeating
broad 600-second briefs or rediscovering existing live proof.

T19 should author specific migration/interruption acceptance before dispatch.
Keep host discovery proof separate from live executor proof; [T14](T14-EVIDENCE.md),
[T16](T16-EVIDENCE.md) and [T17C](T17C-EVIDENCE.md) record existing coverage.
macOS, live POSIX providers and live mid-process recovery remain unverified.
T20 owns final documentation/version/release candidate; 0.3.0 in the T18 preview
is only a proposed inspectable version. M5 remains open. Preserve exact models,
generated-file policy, recovery artifacts and one-slice token checkpoints.
