# Current handoff

Updated 2026-09-29. **T01–T20 and M1–M6 complete**, including selected optional
T15/T16. Branch `refactor/codex-support`, remote `public`. Stop at the token
checkpoint. No implementation task remains in this plan; publication is separate.

Read [candidate/signoff](T20B-CANDIDATE.md), [tracker](TRACKER.md) and
[support matrix](T19B-MATRIX.md). Final source/package-input commit:
`59722b5c6868dc70a3f937c8aa2b9089dcd92a4b`. [All four Windows/Ubuntu Python
3.11/3.14 jobs and every Test/generator/freshness/plugin/catalog gate passed](https://github.com/jhesham/cross-llm-delivery/actions/runs/36437852261).
Exact metadata: `.cld/t20b/ci-final-jobs.json`. The later signoff commit changes
planning documentation only; it does not change tested engine/package inputs.

Version **0.3.0 is prepared**, not published. Seven local artifacts are in
`dist/candidate/`: committed source ZIP, wheel, sdist, both host skill ZIPs and
both plugin ZIPs. Their hashes/build tools and reproducible-content commands are
in the candidate document and `dist/candidate/manifest.json`. Isolated installed
wheel, eight provider resources, four ZIP repeat checks, eight skill validators
and two worked-example previews pass. Thirteen new packaging cases cover the
missing Codex Claude catalog entry, concise entries and native release handling
of Git-versioned Claude manifests; 64 focused release checks pass.

All four **Claude Code user-global standalone skills** now come from `59722b5`:
`C:\Users\Administrator\.claude\skills\cross-llm-<provider>` for antigravity,
cursor, opencode and codex. Entire installed inventories match generated hashes;
38 shared core Python files match across all four; installed help and exact
Luna/max/fast parser/factory checks pass. Backups and original/new hash manifests:
`C:\Users\Administrator\.claude\skill-backups\t20b-20260929-004212-bb64c028`;
duplicate `.cld/t20b/claude-install.json`. Restart Claude Code for discovery.
Older Claude entry estimates fell from ~5.6–6.3k to ~1.2k (79–82% reduction);
Codex-host entries are ~0.8k. Characters/4 are estimates, not billed usage;
references consume additional context when opened. Preserve active ledger state
before rollback; old engines cannot read schema-2 state. Do not mix bundle
engine revisions on one ledger or hand-edit installed files.

[T20A](T20A-EVIDENCE.md) implements `codex:gpt-6-luna@max+fast` with separate
validation identity and explicit effort/tier config. Exposed unsupported/fallback
warnings or actual-tier mismatch fail dispatch; missing tier telemetry cannot
prove delivered fast processing. Deadline remains 600 seconds, explicitly
configurable with `CLD_DISPATCH_TIMEOUT=1200`; probes remain 30 seconds. No
automatic timeout/budget increase, silent tier/model substitution or paid retry.

Evidence limits: prior recorded Windows host discovery and live Kimi K3/OpenCode
and tier-unspecified Luna/max executor evidence remain valid for their recorded
versions. New fast-tier live service, refreshed Claude picker discovery, fourth
Codex-plugin discovery, live Claude-lead execution, live provider mid-process
interruption, Ubuntu Codex flags/live POSIX and macOS remain **unverified**.
Offline CI cannot establish live entitlement. [Migration/recovery](../../MIGRATION.md)
and [rollback evidence](T19B-ROLLBACK.md) retain the tested safety boundaries.

T20A/T20B were direct lead work after the earlier documented Kimi no-candidate
timeouts. No new provider call or subagent; additional provider usage/cost zero;
lead counters unavailable. Do not infer a future dogfood/canary authorization.

Only the authorized refactor branch was pushed. No main merge/sync, tag/release,
provider-mirror publication or Codex user-global install. Read-only preview:
`.cld/t20b/publish-preview.json`; main was
`67ad2f5815e106d0f2f84bfc9f896807411f81e6`, with no `v0.3.0` tag. Review current
remote states again before any separately authorized promotion. The release
helper only bumps to a newer version, so do not request prepared 0.3.0 through
that bump path; see the candidate's publication boundary. No force-replacement
or publication is authorized by these notes. **Pause here.**
