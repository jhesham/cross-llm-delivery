# T20A — Explicit Codex fast tier and coherent Claude installs

Started 2026-09-28, verified 2026-09-29. Parent T20 remains open for T20B documentation/candidate work.
Baseline `d78c734`; engine source
`6c814e5e71de7e806a4ff7564c5c2b19cd3c3da2`, branch `refactor/codex-support`.

## Implemented feedback

- [x] Both executor parsers use one `@effort[+fast]` grammar. Exact
  `codex:gpt-6-luna@max+fast` becomes separate model, effort and service-tier
  kwargs. Unknown/empty/multiple tier suffixes and non-Codex tiers fail locally.
- [x] Default, per-slice and rung factory/admission paths retain the full spec;
  fast and tier-unspecified builds have separate validation evidence/cache keys.
- [x] The Codex invocation emits separate literal configuration arguments
  `model_reasoning_effort="max"` and `service_tier="fast"`. No shell,
  positional prompt, resume, full-access or approval-bypass flag was added.
- [x] Explicit-tier dispatches fail on warning control events or service-tier
  stderr diagnostics even with exit zero and a completed turn. Reported actual
  tiers other than fast/priority fail. No failed-tier diff is collected; partial
  files and process artifacts remain available. Model prose is not a warning.
- [x] Existing `CLD_DISPATCH_TIMEOUT` already supports longer max-effort work.
  Offline adapter proof: explicit 1200-second dispatch with unchanged 30-second
  probes. Defaults stay 600/30 seconds; budgets and paid retry permissions do
  not increase. Setup/core references contain PowerShell and POSIX examples.
- [x] Both host bundles and all four plugin packages regenerated, with tracked
  Claude plugin freshness passing. Claude bundles now also vendor named
  provider/setup references, fixing the Codex fragment's reference destination.
- [x] All four Claude Code standalone skills installed together from the same
  committed engine after regeneration. Codex was absent from the actual global
  Claude skills directory; the three existing skills were preserved in backups.
- [x] Exact-source Windows/Ubuntu Python 3.11/3.14 full-suite and artifact CI.

The optional static Luna picker entry was not added: the Codex provider still
has no authoritative account-scoped model catalog or guessed default. Passing
the explicit executor works; installing the skill makes it available for host
discovery in a new session, but actual picker discovery has not been observed.

## Tests and packages

`tests/test_t20a_codex_fast.py`: 30 new offline cases cover both parsers, rejected
suffixes, durable validation identity, exact arguments, pre-process rejection,
zero-exit warning refusal with real Git partial edits and forbidden diff
capture, actual-tier mismatch, prose isolation, longer bounded dispatch and
both isolated host bundles. Synthetic JSONL/process fixtures are not a live
Codex warning capture.

Local focused coverage: 87 parser/contract/adapter/wiring cases plus 112
admission/model/generator/eight-bundle matrix cases, all passing after the
freshness case was rerun following final reference regeneration. One initial
collection invocation used an incorrect test-helper import; corrected to the
existing `tests` package. No production runtime repair followed these tests.
`git diff --check` passed.

Generation from source commit `6c814e5`:

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex
python generator/check_plugins_fresh.py --dist-root dist --plugins-root plugins
```

## Local installation and rollback

Destination: `<home>\.claude\skills\cross-llm-<provider>` for
antigravity, cursor, opencode and codex. All four SKILL banners identify engine
`6c814e5`, v0.2.0. Generated source remains the monorepo; installed files must
not be edited independently.

Preserved originals:
`<home>\.claude\skill-backups\t20a-20260928-234430-a211eefc`.
The local `install-manifest.json` retains SHA-256 inventories of previous and
new files; `.cld/t20a/claude-install.json` holds the same installation record.
These machine-local manifests/backups are not published. All four bundles were
staged/hash-checked before replacement, and the installation helper restores
originals on a replacement failure. Existing custom files remain in backups.

Verification: installed file inventories match generated bundles; all 38
shared engine Python files match across four skills; four installed `--help`
checks passed; the installed Codex factory resolved exact Luna/max/fast without
an inference call. No Codex user-global installation, marketplace installation
or other skill directory was changed. Restart Claude Code before expecting the
new skill to appear; do not mix old cached skill instructions with this engine.

For rollback, stop delivery writers first, preserve current ledgers/worktrees,
and keep copies of the new installed skills before restoring saved directories.
Restoring old skills does not downgrade a schema-2 ledger: follow
[the rollback guide](T19B-ROLLBACK.md), especially after any new accepted work.
T20B must refresh the complete four-skill set together if engine/docs change.

## Evidence level, CI and usage

Configuration checked against the official
[Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
on 2026-09-28: `service_tier` is a preference; fast maps to priority. CLD catches
exposed warnings/mismatch, but cannot prove actual fast service or detect an
unreported server downgrade when the CLI provides no actual-tier telemetry.
The user-supplied report motivated synthetic failure cases; account/model fast
entitlement and live warning behavior remain unverified in this sitting.

[Exact engine-source CI run](https://github.com/jhesham/cross-llm-delivery/actions/runs/36430643297)
passed all four full-suite jobs and all six test/generator/plugin gates per
job at exact source SHA `6c814e5e71de7e806a4ff7564c5c2b19cd3c3da2`.
Complete job metadata is saved in `.cld/t20a/ci-final-jobs.json`. Every Claude
skill uses this tested engine source. Subsequent handoff/tracker-only commits
do not change engine or generated bundle bytes.

Lead work was direct after T18/T19A/T19B's three documented Kimi no-candidate
timeouts. No automatic paid retry, model substitution, new live Codex canary
or subagent was used. Additional provider calls/tokens/cost: zero. Lead token
counters unavailable; 8–12k was a planning allowance, not a usage measurement.
Stop for explicit token confirmation before T20B. No main merge, tag, release
or provider-mirror publication was performed.
