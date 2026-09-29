# Current handoff

Updated 2026-09-29. **T01–T20 and M1–M6 complete; v0.3.0 published and promoted.**
[Release](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.0) · [publication evidence](PUBLICATION-0.3.0.md).

Immutable tag/source: `81327cc90271bd6126e85e20533e1d9bb874ed08`.
[All four exact-source Windows/Ubuntu Python 3.11/3.14 CI jobs and all 24
required steps passed](https://github.com/jhesham/cross-llm-delivery/actions/runs/36531725348). Seven release artifacts plus manifest/checksums
were uploaded; all nine downloads match local SHA-256 hashes. Local files:
`dist/release-v0.3.0/`; operational evidence: `.cld/publication/`.
The publication signoff commit changes planning documents only; current main
may carry those docs after the immutable release source.

The initial promotion exposed wrapper removal from the public tree. Fix
`7c7abba` retains checked release/sync wrappers; the real local-remote regression
was red before the fix, and all 64 focused release checks pass afterward.
The corrected promoted/tagged commit passed the full four-job suite. No force
push, provider-mirror publication, global installation change or model call.
Lead counters unavailable; provider usage/cost zero.

All four previously installed Claude standalone skills remain coherently from
`59722b5` with their T20B backups/hashes; release engine/skill sources match that
candidate. New downloadable bundles all come from the tagged revision. Restart
the host after replacing a complete coherent skill set. Preserve active state
before rollback; old engines cannot read schema-2 ledgers. Installed-copy edits
and mixed engine versions remain unsupported.

Exact `codex:gpt-6-luna@max+fast` parsing/validation identity and warning/mismatch
failure behavior are covered offline. Fast-tier live delivery, refreshed Claude
picker/fourth Codex-plugin discovery, live Claude-lead execution, live provider
mid-process interruption, Ubuntu Codex flags/live POSIX and macOS remain
unverified. [Support matrix](T19B-MATRIX.md) and
[migration/recovery](../../MIGRATION.md) retain those boundaries. Dispatch remains
600 seconds with explicit timeout configuration; no automatic usage/deadline
increase or silent model/tier substitution.

No planned implementation or publication work remains. **Pause at the token
checkpoint; do not start another task or canary automatically.**
