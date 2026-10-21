# v0.5.0 publication — 2026-10-22

**Published:** [Cross-LLM Delivery v0.5.0](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.5.0), stable and Latest.
Tag `v0.5.0` and public `main` resolve to `968ba335d588165cefe8f4b0c174817e64b5f0fb`, synced by the checked
release workflow from source `bb192c2` (identical tree) with `main` expected at `b1f215f` (v0.4.3); no force
push or retagging. Exact-SHA [CI run 39611482934](https://github.com/jhesham/cross-llm-delivery/actions/runs/39611482934) passed.

This release adds evidence mode ([SPEC](SPEC.md), [PLAN](PLAN.md)): `--ask` tasks and plan slices of
kind investigate, query and materialise, `cld-environments.json`, the fail-closed SQL runner, approvals,
evidence bundles and the knowledge-base starter template. See the [CHANGELOG](../../../CHANGELOG.md).

## Verification

- Four external review rounds of the evidence-mode branch; every finding closed or, where it fails
  closed, recorded in [KNOWN-ISSUES](../../../KNOWN-ISSUES.md).
- Local full suite on the final source before release: **1660 tests, 0 failures, 5 skipped**; the
  release workflow's own full-suite gate also passed.
- Live test on Windows against a local PostgreSQL 17 (`psql --csv`, throwaway database, synthetic data,
  removed afterwards), with a Codex executor: a sandbox query returning the expected values, a CREATE on
  a `real` environment held for approval without touching the database, the approved statement refused
  by the read-only role, and a plan with a query slice followed by a dependent code slice integrated.
- The release workflow now regenerates plugins before its test run (it previously failed the
  plugin-freshness tests on every bump); a regression test pins the order.

## Assets

Built from a clean checkout of `968ba33`. Generated skills and plugins for both hosts were rebuilt there;
restaging them left the tree identical to the tag (`3c01cd4`), differing only in line endings on disk.
The wheel passed an isolated install check (`python -I -S`, five providers, no optional dependencies);
the four bundle/plugin ZIPs rebuilt byte-identically. Nine assets were uploaded and downloaded back; all
hashes match. Assets were scanned for local paths and personal references before upload.
Built with Python 3.13.13, pip 26.0.1, setuptools 82.0.1.

| Asset | SHA-256 |
|---|---|
| `SHA256SUMS.txt` | `c60c98b0ed68a381a5b827726f9a58bbf06e77cd021fe1ed728056b7a4cf6fcb` |
| `manifest.json` | `6c4880945edb1a41ba01bf9554f38d1ba51d4cbe924c18666cebae617c676fa6` |
| `source.zip` | `e53ab96a1bd18264347c666f80eb2eff81bcff26f4f7890647fe53cc305a6049` |
| `cld-0.5.0-py3-none-any.whl` | `0c1a8271fe273356144b88dd6c378f0f76dca27b5e3f537676c1fd691e8b5b6a` |
| `cld-0.5.0.tar.gz` | `6b5bdd8c3e56464b001a04f4496174b3b45a25b928880391d224525ed7c92261` |
| `claude-skills.zip` | `ee37ad822b2a77ea02ddd98b5272f2a76bf08700395492e997ec676a54c93b27` |
| `codex-skills.zip` | `54add3589cb5ebee1b9e10542840fb57cf6c1f1f9596b21eaf4f6773ddead5de` |
| `claude-plugins.zip` | `ccb30e323ab29f9cfcab13d356c90f01ad734f584c940b4a6e2dff69f9699044` |
| `codex-plugins.zip` | `4ee5269fb84ccbbe65710969d845bd1d48e1bd5a0c7c38fc55d269eca460c7fe` |

## Boundaries

Evidence mode is live-tested only on Windows with PostgreSQL; BigQuery and MCP-only environments are
offline-tested. Existing installs must refresh their bundles or plugins to use v0.5.0. This receipt is
committed after release; the tag remains on the tested source.
