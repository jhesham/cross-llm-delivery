# v0.5.1 publication — 2026-10-22

**Published:** [Cross-LLM Delivery v0.5.1](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.5.1), stable and Latest.
Tag `v0.5.1` and public `main` resolve to `50344cabf74fdb3afc92e8ac158a253ed0dd76fb`, synced by the checked
release workflow from source `a1bb40b` (identical tree) with `main` expected at `eb6e4d9` (v0.5.0 record); no
force push or retagging. Exact-SHA [CI run 39774019841](https://github.com/jhesham/cross-llm-delivery/actions/runs/39774019841) passed.

This release fixes problems found when installing v0.5.0 on a second Windows machine and adds opt-in gateway
mode for the Claude executor. See the [CHANGELOG](../../../CHANGELOG.md).

## Verification

- Failing tests were written first for every fix; Codex slices ran on `codex:gpt-6.1-sol@high`, the rest on
  `codex:gpt-6-luna@max+fast`.
- Two external review rounds of the release range: seven findings in the first round, all closed in the
  second (managed-gateway identity, installer update fallback, MCP disclosure).
- Local full suite on the final source: **1710 tests, 0 failures, 5 skipped**; the release workflow's own
  gate also passed.
- Codex executor isolation was checked without model calls against Codex CLI 0.163: with CLD's switches,
  plugin-provided MCP servers disappear, configured servers are disabled, the isolated features are off and
  the shell, exec and fast-tier features stay on.
- Gateway mode is tested offline only; no gateway was available on the release machine.

## Assets

Built from a clean checkout of `50344ca`; regenerated skills and plugins left the tree identical to the tag.
The wheel passed an isolated install check (`python -I -S`, five providers, no optional dependencies); the four
bundle/plugin ZIPs rebuilt byte-identically. Nine assets were uploaded and downloaded back; all hashes match.
Assets were scanned for local paths and private references before upload.
Built with Python 3.13.13, pip 26.0.1, setuptools 82.0.1.

| Asset | SHA-256 |
|---|---|
| `SHA256SUMS.txt` | `f635e9789b83353fcc8a456d7f85e8b626c0b3ea3df56061cba35fcc30054aa2` |
| `manifest.json` | `412cc1d2bce015036c9471b616270681779aaac25d09f3b7fe509afafdb1bf22` |
| `source.zip` | `4825a40fa24326da53aa3626339055353781e5ee8d83ecf876a5154c1045673e` |
| `cld-0.5.1-py3-none-any.whl` | `3f1d48f44e6c750f3faa05fab6bc0d9a69818c67e2a175fc43307c180ecef620` |
| `cld-0.5.1.tar.gz` | `16aa3bce74cfc47edb42b06544cd2b35e41c361f9051b3a0afdcec0d0aa71a94` |
| `claude-skills.zip` | `fc08331418f5d1f145d5c9059127f5e24699d02cee8bceb2dca3b6ea3758a902` |
| `codex-skills.zip` | `c1f4f914800e17c90ac7e302035da5912b90f68abb22f12e4fb2dcf1affcb3ad` |
| `claude-plugins.zip` | `db127dcbd9633f697c518cf375f661cf612a10228fe63a242ccc4878e96dce0f` |
| `codex-plugins.zip` | `c9bed4d34917d7c6c3b46315fc9b503ad0318676bebd3c7bc9857ac5a17d16cd` |

## Boundaries

Gateway mode and the reduced Codex executor input footprint still need a live run on a machine with a
gateway. Existing installs must refresh their bundles or plugins to use v0.5.1. This receipt is committed after
release; the tag remains on the tested source.
