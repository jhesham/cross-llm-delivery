# v0.5.3 publication — 2026-11-04

**Published:** [Cross-LLM Delivery v0.5.3](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.5.3), stable and Latest.
Tag `v0.5.3` and public `main` resolve to `84c356cd1c95e43853099c6ccfa3a20a0641c655`, synced by the checked
release workflow from source `810bb93` with `main` expected at `4dfc143` (repository icon commits); no force
push or retagging. Exact-SHA [CI run 41826043490](https://github.com/jhesham/cross-llm-delivery/actions/runs/41826043490)
passed.

This release removes credential handling from telemetry export and the optional grading helper, and adds
plugin-directory listing fields to the Claude Code plugin manifests. See the [CHANGELOG](../../../CHANGELOG.md).

## Verification

- Failing tests were written first; both code slices ran on `codex:gpt-6-luna@max+fast` and passed on the
  first attempt.
- One external review round of the release range: four findings (an overbroad no-credentials claim and a
  scan that missed some lookup forms, telemetry wording that did not cover the OpenTelemetry SDK's own
  header handling, a live OTLP test that inherited ambient headers, and a live grading test that lost its
  key). All four were addressed; a re-check closed three and the remaining wording was narrowed as the
  reviewer suggested.
- Local full suite: **1749 tests, 0 failures, 5 skipped**; the release workflow's own gate also passed.
- The shipped assets contain no explicit lookup of a credential-named variable. Validation fingerprinting
  and the Claude gateway presence check still read credential values locally, as PRIVACY.md describes.
- All five Claude plugin manifests pass `claude plugin validate --profile directory` (CLI 2.1.318), with
  only the non-blocking missing-icon warning.
- The Langfuse collector recipe is checked against Langfuse's documentation only; no live collector run.

## Assets

Built from a clean checkout of `84c356c`; regenerated skills and plugins left the tree identical to the tag.
The wheel passed an isolated install check (`python -I -S`, five providers, no optional dependencies); the four
bundle/plugin ZIPs rebuilt byte-identically. Nine assets were uploaded and downloaded back; all hashes match.
Assets were scanned for local paths, private references and credential lookups before upload.
Built with Python 3.13.13, pip 26.0.1, setuptools 82.0.1.

| Asset | SHA-256 |
|---|---|
| `SHA256SUMS.txt` | `cf446fb758edc0057eb2f7f7ec56ce912e9e122c4589f882ac3a0ca85171a723` |
| `manifest.json` | `144584cd091222501676dabc03085c4604ad7bc0eebb39a4327d7c3e3f51f7c5` |
| `source.zip` | `440ef6d420f7942a2ad87f6318a57e97476d4de6cd3996ecc204417ca252d03a` |
| `cld-0.5.3-py3-none-any.whl` | `fbb665bc9f2263a2d2532aab3bd487980537bb9ff3a17b423b06eec6e5a65525` |
| `cld-0.5.3.tar.gz` | `65fec716eff8a647aabfe5c39a9f15565a043894973ff52940dfb6d4d568aef2` |
| `claude-skills.zip` | `e2177864bb3e3fa6a70d36259c0f42b263e468841e163d2bbb04befba2bb77d2` |
| `codex-skills.zip` | `dfc206f1981f7cc1109f876920081946f36d2ffe5c00365c456c0ec0004c40d1` |
| `claude-plugins.zip` | `b884eee047d1cb3cfc3dd85e6d07fc08df824867ac36a97b1c4736182ecc71ce` |
| `codex-plugins.zip` | `7d5a9b309cbcd3cda5c1a05fe72828f8ce9fb2188d9e8545568efc52d06fe8bd` |

## Boundaries

Langfuse export through the collector and gateway mode still need live runs. Existing installs must refresh
their bundles or plugins to use v0.5.3; a Langfuse setup that relied on the removed key shortcut must move to
a collector or the standard OTLP variables. This receipt is committed after release; the tag remains on the
tested source.
