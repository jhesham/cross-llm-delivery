# T20B — 0.3.0 release candidate

Version 0.3.0 is prepared on `refactor/codex-support`, remote `public` at
`https://github.com/jhesham/cross-llm-delivery.git`. Candidate assembly and final
source CI are in progress; no release/tag/default-branch publication is implied.
The exact tested source SHA, artifact hashes and expected target state will
be filled below after assembly and verification. Do not publish a pending gate.

## Rebuild procedure

Check out the recorded source commit in a clean clone. Use Python 3.11+ and
the recorded build-tool versions. Standalone target bundles need no pip install;
the source build uses installed setuptools/pip with no runtime/API dependency.

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex
python generator/check_plugins_fresh.py --dist-root dist --plugins-root plugins
python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist/candidate
python -c "import setuptools.build_meta as b; b.build_sdist('dist/candidate')"
git archive --format=zip --output=dist/candidate/source.zip HEAD
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
repository: `jhesham/cross-llm-delivery`. Exact source and expected target SHAs
must be reviewed immediately before any authorized promotion. Do not force
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

- [ ] Source/version/package/plugin metadata agree; exact source recorded.
- [ ] Eight skills and both plugin archives assembled with source/wheel/sdist.
- [ ] SHA-256 manifest, isolated installed-wheel/core check and entry sizes saved.
- [ ] All four exact-source CI jobs and all artifact gates pass.
- [ ] All four Claude Code standalone skills refreshed from that tested source,
  with backups and installed hash checks.
- [ ] Original review items and T20/M5 tracker closed against this evidence;
  missing live/discovery surfaces retained as limitations.
