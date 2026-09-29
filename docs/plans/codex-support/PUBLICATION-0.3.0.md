# 0.3.0 publication — 2026-09-29

**Published:** [Cross-LLM Delivery v0.3.0](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.0). Stable release, not a draft
or prerelease. Tag `v0.3.0` resolves to `81327cc90271bd6126e85e20533e1d9bb874ed08`.
The release is marked latest; all nine uploaded assets were downloaded and
SHA-256 checked against their local originals.

## Promotion and verification

Prior main: `67ad2f5815e106d0f2f84bfc9f896807411f81e6`.
Initial promotion `a6b8f22` failed its two Ubuntu wrapper tests because the sync
helper omitted `release.ps1` and `sync-public.ps1`. The failed run
[36531055073](https://github.com/jhesham/cross-llm-delivery/actions/runs/36531055073)
was cancelled after diagnosis; no tag/release was created from that commit.
The helper now retains its checked wrappers and only omits `SHIP-PLAN.md`.
The real local-bare-remote regression failed before the fix and passed afterward;
all 64 focused T18/T20B cases passed. Fix source: `7c7abba`.

Corrected promotion: `81327cc90271bd6126e85e20533e1d9bb874ed08`, normal fast-forward pushes only.
[Exact main CI](https://github.com/jhesham/cross-llm-delivery/actions/runs/36531725348) passed Windows/Ubuntu × Python 3.11/3.14:
four jobs and all 24 Test/generator/freshness/plugin/catalog steps. Branch
source had already passed CI at `8a63513`; publication changes were documentation
and the independently tested wrapper-preservation fix. No redundant local full
suite was run; the promoted commit passed the full suite on all four CI jobs.

All release assets were rebuilt from the tagged commit, separately from the
historical T20B candidate. Wheel/sdist include all eight provider Markdown
resources. The installed wheel passes `python -I -S` outside the checkout,
four-provider import, optional-dependency-free core, exact fast parsing and CLI
help. Eight skills pass generator isolation; Claude plugins pass freshness;
both four-provider plugin catalogs assemble; four repeated bundle ZIPs match.

## Published assets

| File | SHA-256 |
|---|---|
| `source.zip` | `f1e40abf102109a40f3f8f8aedf5859302cf8bea514350eb56b6d55aa22a5db0` |
| `cld-0.3.0-py3-none-any.whl` | `41bafb73a1da2ed55d67dea4b3dcc1ec171cbff1f9815482bf1f5c101b57ceaf` |
| `cld-0.3.0.tar.gz` | `465ef0d56064fd3cb1e92f40e79a30c41de3961b6e919914ee493d105b65a70a` |
| `claude-skills.zip` | `a9ca8599939609e40ca8ce54b1f5b63f97a8b070f9f7cc0f549b4b0e917e2279` |
| `codex-skills.zip` | `c72b71e03a82bf1102f8ff8ea9451b50f878508717f29af4f6d6156119b5e32a` |
| `claude-plugins.zip` | `b3365b01645c9cf85f43d67f480274613a7c9a6371a9fc4c967e39b41b0652fc` |
| `codex-plugins.zip` | `dff157c27d13c642ff36ffe9cf32a3779ed680f5a43c6cfa12cfb7fe3b2fc8b2` |
| `manifest.json` | `e2a2740d92b3778f5b804a1d3fd137d6359bf8aead44c18aa863917ad97a5950` |
| `SHA256SUMS.txt` | `9ccce98e2d63a381343f0b9a35aa8a4ec7e7929b9b77b3606995dcad4e1a612f` |

Local release directory: `dist/release-v0.3.0/`.
Build: Python 3.13.13, pip 26.0.1, setuptools
82.0.1; source ZIP is Git-canonical committed content.
`manifest.json` records source, version, provenance, entries and artifact hashes;
`SHA256SUMS.txt` covers the seven binary/source artifacts. Both metadata files
were also downloaded and checked. Artifact bytes need not match builds using
different Python/build tools or line-ending settings.

## Handoff and boundaries

T01–T20 and M1–M6 remain complete. The publication signoff is a later
**planning-documents-only commit**; the immutable tag retains the tested source
above. Current main may include those later signoff docs. No engine, package,
generated skill or test input changes after the release gate.

Previously installed four Claude skills remain coherently at engine `59722b5`;
no global installation was changed during publication. Release engine/skill
sources match that candidate; all newly downloadable bundles use the tagged
source revision. Provider mirrors and Codex global installation were not part
of publication. No provider/model calls or subagents; provider usage/cost zero,
lead token counters unavailable. Stop at this checkpoint.

Live fast-tier delivery, refreshed Claude picker and fourth Codex-plugin
discovery, live Claude-lead execution, live provider mid-process interruption,
Ubuntu Codex flags/live POSIX and macOS remain unverified. See
[support matrix](T19B-MATRIX.md), [candidate preparation](T20B-CANDIDATE.md) and
[migration/recovery](../../MIGRATION.md); publication does not expand evidence.

Local operational evidence: `.cld/publication/ci-final-jobs.json`,
`promotion-result-fixed.json`, `release-commands.log`, `release-verification.json`,
`release-asset-hashes.json`, downloaded assets and red/green regression logs.
The first failed native helper stopped without reporting success and retained
its recovery worktree; it was not deleted or force-pushed away.
