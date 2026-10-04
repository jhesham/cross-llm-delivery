# v0.4.2 publication — 2026-10-04

**Published:** [Cross-LLM Delivery v0.4.2](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.2), stable and Latest.
Annotated tag `v0.4.2` resolves to `64048696c4bce27e8b1119137a630e9b3c6164fa`. Public main was promoted by normal
fast-forward from `7372fdb37f54044a63ad061024da3945280540ff`; no force push or retagging.

This release includes all N04–N08 fixes and the F01 pytest diagnostics follow-up:
frozen candidate imports, Codex configuration identity, five-provider recursion
protection, native Windows OpenCode discovery, native POSIX Antigravity cwd and
pytest process classification. All five providers remain available to Codex and
Claude Code lead hosts. See [implementation checkpoints](REMEDIATION-N04-N08.md).

## CI blocker and verification

The initial F01 [CI run 37142332565](https://github.com/jhesham/cross-llm-delivery/actions/runs/37142332565)
passed three jobs but failed Windows/Python 3.14 when a status reader briefly
blocked `os.replace` during an atomic ledger save. The release includes a bounded
retry and committed regressions for this failure.

Committed regression `b6f65af` had four intended failures and three passes on
the old implementation. Fix `b738983` retries only Windows replacement error
codes 5/32/33, up to ten attempts with 0.65 seconds of total requested backoff.
It reuses the same fully flushed temporary file and retains atomic replacement,
readback verification and cleanup. Other errors fail immediately; persistent
Windows denial remains a failure and leaves the old target intact.

- Focused atomic-write, ledger, concurrency and recovery checks: **49 passed**.
- Local final-source full suite: **1386 passed, 5 skipped, 1 deselected, 2 warnings in 1704.86s (0:28:24)**.
- Release branch source/artifacts `7cbb825`:
  [CI run 37173679953](https://github.com/jhesham/cross-llm-delivery/actions/runs/37173679953),
  all four jobs passed before promotion.
- Promoted/tagged source `64048696c4bce27e8b1119137a630e9b3c6164fa`:
  [exact-main CI run 37175031531](https://github.com/jhesham/cross-llm-delivery/actions/runs/37175031531),
  all four Ubuntu/Windows × Python 3.11/3.14 full-suite, generation, freshness and
  packaging jobs passed before tag/publication.

The prior focused groups overlap these full-suite cases; do not add their counts.
The checked `generator.release.sync_public` workflow reused the already completed
local full-suite gate, regenerated both hosts/plugins, validated manifest versions,
pushed main normally and required exact-main CI. No test or CI gate was bypassed.

## Assets

Built from a clean checkout of the exact promoted/tagged SHA. All five providers'
skills for both hosts and both plugin archives were regenerated together.
Seven payloads plus manifest/checksums were uploaded and all **nine** downloaded
back; their hashes match local assets. Wheel isolation passed with `python -I -S`,
five providers and no optional dependencies. Four bundle/plugin ZIPs rebuilt
identically. `SHA256SUMS.txt` has LF endings and covers the seven payloads.
All 40 shared engine files also match between the source archive, wheel and ten
skill bundles. The temporary Windows checkout's generated-file index was refreshed
for LF/CRLF bookkeeping, with its entire Git tree proven unchanged before assembly.

| Asset | SHA-256 |
|---|---|
| `SHA256SUMS.txt` | `5068f703a40ffdfd97b9775e2b2ce294de680bba40fa46ae193b5ad819410976` |
| `claude-plugins.zip` | `005fac7eabc040b76089aea6b07470d06b885c6d68c0b5976d8e13cae369393a` |
| `claude-skills.zip` | `8aca29193653e2814f527f6c70abf6a5fd46e2e7db1f981683e7b1a575075ec6` |
| `cld-0.4.2-py3-none-any.whl` | `67b2bf0aac719e8cf5c108b5d89940313b1e307fcb5d4ed1755b30457b788567` |
| `cld-0.4.2.tar.gz` | `07687135496f47db3a74bb5ec62d8a88ba48d07f1da5e56972d18add6759f11c` |
| `codex-plugins.zip` | `7cf6e6153319305944f05062a6adde91d9caa03301037380f9250a553ab1fdfd` |
| `codex-skills.zip` | `95a7a05caf9f130012576ef369ea897edb7dc762478ed6af77e79d429acc7716` |
| `manifest.json` | `11ec62552e099114b17cbc4827ed02a206c2fd1a23f83281fee17247bd9e3aa1` |
| `source.zip` | `e0818daa8d455a4758250f46fc668f57aa6e2cb402b7d70b46dcd38c54d99afc` |

Local assets: `dist/release-v0.4.2/`; private command, CI and downloaded-hash
evidence: `.cld/publication-0.4.2/`. The publication receipt is committed after
release; the immutable tag remains on the tested runtime/assets source.

## Boundaries

No provider/model calls, global skill installation, persistent Codex configuration
changes or cleanup of retained failed delivery worktrees were performed for this
release. Existing installs must refresh their bundles to use v0.4.2; bundles
sharing one ledger should come from the same engine revision. Live POSIX/macOS
provider behavior and independent fast-tier routing telemetry remain unverified.
