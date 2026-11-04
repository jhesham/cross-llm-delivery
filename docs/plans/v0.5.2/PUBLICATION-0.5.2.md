# v0.5.2 publication — 2026-11-04

**Published:** [Cross-LLM Delivery v0.5.2](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.5.2), stable and Latest.
Tag `v0.5.2` and public `main` resolve to `8171078b27731d592b45a86ed491caed355f860f`, mirrored from source
`8d0cb38`; no force push or retagging. Exact-SHA [CI run 41803265349](https://github.com/jhesham/cross-llm-delivery/actions/runs/41803265349)
passed on all four runners (Windows and Ubuntu, Python 3.11 and 3.14).

The first release attempt synced `main` to `f2c7c8b` and stopped before tagging: one new test passed locally
only because the release machine has the `claude` CLI on PATH, and failed on CI runners without it. The test
now fakes that lookup; nothing was tagged or published from `f2c7c8b`, and `main` moved forward from it
normally.

This release fixes problems found when running v0.5.1 in Claude gateway mode on a second Windows machine.
See the [CHANGELOG](../../../CHANGELOG.md).

## Verification

- Failing tests were written first for every fix; Codex-specific slices ran on `codex:gpt-6.1-sol@high`, the
  rest on `codex:gpt-6-luna@max+fast`.
- A driver-level test runs `--step` in gateway mode with a gateway model ID through spec parsing and
  admission to the executor, the path the v0.5.1 tests missed.
- One external review round of the release range: three findings (dry-run Codex spec checks, command output
  written into the worktree, control characters trimmed before validation), all closed and re-checked.
- The release workflow's local full-suite gate and exact-SHA CI passed.
- The Codex scratch folder's writable-root grant was checked without model calls using `codex sandbox`.
- Gateway mode is tested offline only; no gateway was available on the release machine.

## Assets

Built from a clean checkout of `8171078`; regenerated skills and plugins left the tree identical to the tag.
The wheel passed an isolated install check (`python -I -S`, five providers, no optional dependencies); the four
bundle/plugin ZIPs rebuilt byte-identically. Nine assets were uploaded and downloaded back; all hashes match.
Assets were scanned for local paths and private references before upload.
Built with Python 3.13.13, pip 26.0.1, setuptools 82.0.1.

| Asset | SHA-256 |
|---|---|
| `SHA256SUMS.txt` | `9dacf0d1635b209b3f5bf12daa23c4a1c76265d502cbb8316dea930a950cc66c` |
| `manifest.json` | `eb730710cd384a9a53c5fa0127b4eab157824173ecdaeb77cc85e0cd2081a409` |
| `source.zip` | `a9d7345db521ddb01ff560b72b40356b4c6e3d8374d07768bbd2c0017c0ed096` |
| `cld-0.5.2-py3-none-any.whl` | `cc61b2318d66b6a824402b504c6a16e804f5e40282bb677ac4c07b8777af7b21` |
| `cld-0.5.2.tar.gz` | `fa6addac352cba4cd2117100d7faf74906cdee7309279259d15174a010c74492` |
| `claude-skills.zip` | `8f42ff28ad98201f35740fbac3852b21525a9cdeae025fc2e21e0b0106fb2b74` |
| `codex-skills.zip` | `a304d6dc8019a334d08d42e6d97d4b395e13ed923e1a78b33b087c076f0c12a4` |
| `claude-plugins.zip` | `7e561548bf6a2eed5dbb4da706d01c3e8fa313c2134a5f551cae78fc835a2ff5` |
| `codex-plugins.zip` | `d23c16c28ad4c25fb063449fcce8e70845f8a3f4474426950934403c2a0730ea` |

## Boundaries

Gateway mode still needs a live run on a machine with a gateway. Removing the Codex scratch folder is best
effort (see KNOWN-ISSUES). Existing installs must refresh their bundles or plugins to use v0.5.2. This receipt
is committed after release; the tag remains on the tested source.
