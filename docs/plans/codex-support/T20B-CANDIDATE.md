# T20B — 0.3.0 release candidate

Historical preparation record. The subsequently published release has its own
[source/CI and asset hashes](PUBLICATION-0.3.0.md).

Version 0.3.0 is prepared on `refactor/codex-support`, remote `public` at
`https://github.com/jhesham/cross-llm-delivery.git`. Candidate assembly, exact-source CI and
installation checks are complete. T20/M5 are closed; no release/tag/default-branch
publication is implied. The code/package-input source below is tested; the later
signoff commit changes planning documentation only.

## Assembled source and artifacts

Source commit: `59722b5c6868dc70a3f937c8aa2b9089dcd92a4b` on `refactor/codex-support`.
This is the source/package-input revision; the later documentation signoff
commit does not change it. Version `0.3.0` agrees across VERSION,
pyproject, wheel metadata and Codex plugin manifests. Claude manifests follow
Git commits without fixed versions; their generated entry banners must match
VERSION. Four-provider native release validation passes on the real packages.

Artifacts are local under `dist/candidate/`; the manifest is
`dist/candidate/manifest.json`, duplicated at
`.cld/t20b/candidate-manifest.json`. No binaries are checked into Git.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `source.zip` | 1174495 | `804ff8ceb8e6c750e016495adc3fda27d8b398aa4d79b18a35b5871543417a02` |
| `cld-0.3.0-py3-none-any.whl` | 139701 | `a029b0ded7c3aac95f17d016ec10dea69290ca3ca6925b0ecaf70815cf326878` |
| `cld-0.3.0.tar.gz` | 208654 | `bb48d0cd06d4eae884f75b67df056caa78456961e9442ddb01b4d2d4f0f10d02` |
| `claude-skills.zip` | 519576 | `06a20a8d7473797d2c9e3e8d1cc28e8fd09a3db587da2d7db0a2d0b2c74bb9b8` |
| `codex-skills.zip` | 522917 | `96739695855d32b248fc19127be51744ea499da284ccc0653b4358739a5d858c` |
| `claude-plugins.zip` | 534874 | `46445b1dbc05c98f16108ee283cf32b75e254e60015206712beea075b56ac734` |
| `codex-plugins.zip` | 537393 | `03a609a0f9d081ff8b08ddc9ea671b410730db5d652a1d274e03d9dd971ce1ca` |

Build environment: Windows, Python 3.13.13, pip 26.0.1, setuptools
82.0.1. Source ZIP is `git archive` of the exact commit;
wheel/sdist were built from its canonical Git content, without index/network or
runtime dependencies. `SOURCE_DATE_EPOCH` was set to the commit timestamp.
All eight provider Markdown resources occur in both distributions. The wheel
was installed outside the checkout and checked under `python -I -S`:
installed import provenance, four providers, optional-dependency-free core,
CLI help and exact Luna/max/fast parsing all pass. All four bundle ZIPs were
assembled twice with identical per-archive hashes. The build log and local
assembly script are `.cld/t20b/assembly.log` and `.cld/t20b/assemble.py`;
the generator commands below remain the source-controlled rebuild interface.

## Entry context and coherent installation

Entries retain YAML-first discovery and link provider/setup/operational detail
by reference. These are **ceil(characters / 4) estimates**, not tokenizer or
billed-usage measurements; reading references still consumes context.

| Provider | Previous Claude estimate | Current Claude estimate | Entry reduction | Current Codex estimate |
|---|---:|---:|---:|---:|
| antigravity | 5562 | 1179 | 78.8% | 805 |
| cursor | 6341 | 1170 | 81.6% | 793 |
| opencode | 5849 | 1176 | 79.9% | 800 |
| codex | 1631 | 1200 | 26.5% | 822 |

The optional static Luna model-picker entry was not added; Codex continues to
require explicit model/effort selection, with no guessed default or entitlement.

All four Claude Code standalone skills were staged and hash-checked before
replacement, then installed together from `59722b5` under
`<home>\.claude\skills\cross-llm-<provider>`.
Every installed file matches its generated bundle; all 38 shared core Python
files (40 common Python files including wrappers) agree. Installed driver help
passes four times; the installed Codex parser/factory preserves
`gpt-6-luna`, `max`, `fast` without invoking inference.

Backups: `<home>\.claude\skill-backups\t20b-20260929-004212-bb64c028`.
Original/new SHA-256 inventories are in that folder's
`install-manifest.json` and `.cld/t20b/claude-install.json`;
check results and entry measurements are `.cld/t20b/installed-checks.json`.
Restart Claude Code before relying on picker discovery; that discovery is
still unverified. Rollback must preserve active state and does not downgrade
schema-2 ledgers.

## Verification evidence

- Thirteen new T20B offline cases cover the actual four-provider Claude catalog,
  eight concise entries/reference ownership and native release manifest
  validation. The final focused T20B/T18 run passed **64 cases**.
- Two real packaging defects were fixed: missing Codex catalog entry, and the
  native release gate incorrectly requiring a fixed version on intentionally
  Git-versioned Claude manifests. Current banners pass; stale/missing banners
  and an explicit null version fail. Original R/A closure remains in
  [the defect register](DEFECTS.md).
- Eight standalone bundles pass smoke and official skill quick validation;
  four tracked Claude plugins pass freshness; all eight plugin packages and
  catalogs assemble. Regeneration after the source commit is idempotent.
- The worked-example committed baseline fails both protected tests as expected.
  Both host vendored-driver previews report `pending` / code 0 without a
  dispatch. Public documentation links resolve. Results:
  `.cld/t20b/worked-example-preview.json`.
- Full Windows/Ubuntu × Python 3.11/3.14 source CI passed:
  [exact-source run](https://github.com/jhesham/cross-llm-delivery/actions/runs/36437852261).
  All four jobs and all 24 Test/generator/freshness/plugin/catalog steps passed.
  Exact job/step results: `.cld/t20b/ci-final-jobs.json`.

T20B used direct lead work after the earlier recorded Kimi no-candidate
timeouts; no new provider call or subagent. Additional provider usage/cost:
zero. Lead counters unavailable; 10–16k was the planning allowance, not a
measurement.

## Rebuild procedure

Check out the recorded source commit in a clean clone. Use Python 3.11+ and
the recorded build-tool versions. Standalone target bundles need no pip install;
the source build uses installed setuptools/pip with no runtime/API dependency.

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex --out-root dist/release-plugins
python generator/check_plugins_fresh.py --dist-root dist --plugins-root plugins
python -c "from pathlib import Path; Path('dist/candidate').mkdir(parents=True, exist_ok=True)"
git archive --format=zip --output=dist/candidate/source.zip HEAD
python -m zipfile -e dist/candidate/source.zip dist/candidate/source
python -m pip wheel dist/candidate/source --no-deps --no-build-isolation --no-index --wheel-dir dist/candidate
python -c "import os,setuptools.build_meta as b; os.chdir('dist/candidate/source'); b.build_sdist('../')"
```

The source ZIP is the committed tree. For skill/plugin transfer, archive the
generated roots with sorted file paths, fixed ZIP timestamps and no Python
caches. Keep all four skills per host together. The Claude plugin archive must
include the root `.claude-plugin/marketplace.json` and `plugins/`; the Codex
archive must include `.agents/plugins/marketplace.json` and its `codex/` sources.
No ledgers, prompts, process traces, credentials or installation backups belong
in the candidate. Hash each assembled file with SHA-256 and retain its manifest.

Artifact hashes identify the delivered set. A rebuild uses the same committed
source and commands; wheel/sdist bytes can differ across Python/build-tool,
line-ending or archive-metadata versions. Source/bundle contents and manifests
must be checked independently rather than promising cross-tool byte identity.

## Migration and support

See [migration/recovery](../../MIGRATION.md),
[installation](../../../INSTALL.md) and
[recorded evidence matrix](T19B-MATRIX.md). Schema-2 migration is explicit and
backed up; old engines cannot read new state. All bundles writing one ledger
must use the same engine revision. Integration records a candidate ref/SHA
and does not automatically merge the user's checkout.

Offline coverage is Windows/Ubuntu × Python 3.11/3.14 plus eight bundles and
four plugins per host. Historical Windows discovery/live evidence applies
only to recorded versions. New fast-tier live service, updated Claude picker
discovery, fourth Codex-plugin discovery, live Claude-lead execution, live
provider mid-process interruption, Ubuntu Codex flags/live POSIX and macOS are
unverified. No new paid canary is part of T20B.

## Publication boundary

Target ref: `public:refs/heads/main`; proposed tag: `refs/tags/v0.3.0`; release
repository: `jhesham/cross-llm-delivery`. Read-only preview on 2026-09-29 recorded expected main
`67ad2f5815e106d0f2f84bfc9f896807411f81e6` and no `v0.3.0` tag.
Preview evidence: `.cld/t20b/publish-preview.json`. Exact source and expected
states must be reviewed again immediately before any authorized promotion. Do not force
replace public history or publish provider mirrors by implication.

This source already prepares version 0.3.0. The `release` helper is designed to
**bump to a newer version**; requesting 0.3.0 from this prepared source would
correctly fail its version guard. Do not bypass that guard. A separately
authorized publication of this candidate must promote the reviewed source
through a normal branch merge/sync, pass exact-SHA CI on the resulting target,
verify the tag is absent, and then tag/release that verified target commit with
these candidate notes. For the checked sync path, first inspect:

```bash
python generator/release.py sync --source-branch refactor/codex-support --remote public --remote-url https://github.com/jhesham/cross-llm-delivery.git --github-repo jhesham/cross-llm-delivery --target-branch main --no-skills --dry-run
```

A preview does not authorize execution. No main merge/sync, tag/release, mirror
publication or Codex user-global install has been performed for this candidate.

## Assembly and signoff

- [x] Source/version/package/plugin metadata agree; exact source recorded.
- [x] Eight skills and both plugin archives assembled with source/wheel/sdist.
- [x] SHA-256 manifest, isolated installed-wheel/core check and entry sizes saved.
- [x] All four exact-source CI jobs and all artifact gates pass.
- [x] All four Claude Code standalone skills refreshed from that tested source,
  with backups and installed hash checks.
- [x] Original review items and T20/M5 tracker closed against this evidence;
  missing live/discovery surfaces retained as limitations.


2026-09-29 publication update: [v0.3.0 is published](PUBLICATION-0.3.0.md),
with four-job exact-main CI at `81327cc` and nine downloaded asset hashes
verified. The checked sync wrapper-preservation fix (`7c7abba`) is covered by
the red/green local-remote regression and 64 focused release checks. Historical
candidate hashes/installed skills remain distinct from final release assets.
