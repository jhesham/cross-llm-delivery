# cross-llm-delivery (`cld`)

Cross-LLM Delivery lets **Codex or Claude Code lead a build** while a selected
headless CLI implements its slices. The lead writes contracts and committed
acceptance tests; the engine independently verifies each Git candidate, checks
its writable allowlist, and integrates accepted commits against an explicit
test suite. Model output alone never decides acceptance.

The lead host and implementation provider are separate choices:

| Lead host | Implementation provider |
|---|---|
| Codex CLI or IDE, using a Codex skill bundle | OpenCode, Antigravity, Cursor or Codex CLI |
| Claude Code, using a Claude skill or plugin | The same four providers and engine |

Version **0.3.0** supports both lead hosts and all four executor providers.
Use the [versioned release and artifacts](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.3.0)
for a fixed source revision; marketplace installs follow `main`.
[Candidate verification record](docs/plans/codex-support/T20B-CANDIDATE.md).

## Install and select

You need Python 3.11+, Git, the chosen lead host, and the chosen provider CLI
with suitable authentication. Bundles vendor their engine: no Python package
install is needed on the target machine. Install only the providers you use;
refresh all bundles sharing a ledger from the same source revision.

```bash
python generator/build_skill.py --all                 # Claude Code skills
python generator/build_skill.py --all --host codex    # Codex skills
python generator/build_plugins.py                    # Claude plugins
python generator/build_plugins.py --host codex        # Codex plugins/catalog
```

[INSTALL.md](INSTALL.md) covers Claude standalone/plugins, Codex standalone
CLI/IDE and the separate Codex plugin surface. Provider catalog entries are
snapshots; select an exact supported CLI model rather than assuming an account
can run every entry. Codex has no guessed model default or static catalog.
For the requested Luna setting, use `codex:gpt-6-luna@max+fast`;
unknown tiers fail locally and exposed tier warnings/fallbacks fail dispatch.
Actual fast processing remains unverified when CLI telemetry cannot establish it.

## Author a plan

Commit failing acceptance tests before dispatch. This is a valid two-slice
plan; briefs are single lines and lists are comma-separated relative paths.

```markdown
## SLICE: A
brief: Implement normalize_name(value) in src/names.py so tests/test_names.py passes; do not edit tests.
files: src/names.py
acceptance_test_path: tests/test_names.py
deps:

## SLICE: B
brief: Use normalize_name in src/report.py so tests/test_report.py passes; preserve the existing API.
files: src/report.py
acceptance_test_path: tests/test_report.py
deps: A
```

Optional fields are `executor`, `complexity` (`easy|standard|complex`),
`protected_inputs`, and `allow_already_satisfied: true|false`.
An already-green baseline is rejected unless explicitly allowed; a no-change
candidate must still pass independent acceptance. Nested `SUBSLICE` blocks,
multiline briefs, unknown/repeated fields, unsafe paths and cyclic/missing
dependencies are rejected. [Plan guide](skill/references/authoring-plans.md).

## Drive, inspect and integrate

From an installed skill directory, use absolute plan/repo paths:

```bash
python scripts/run_delivery.py <plan.md> --repo <dir> --dry-run --json
python scripts/run_delivery.py <plan.md> --repo <dir> --step --workers 1 --executor <exact-spec> --validation-policy allow --budget-attempts 2 --json
python scripts/run_delivery.py --status --repo <dir> --json
python scripts/run_delivery.py <plan.md> --repo <dir> --integrate --integration-tests <committed-pytest-selector> --json
```

The dispatch example assumes the user authorized that exact model and at most
two calls, including any validation. Choose limits for the actual build; two
calls are not a guarantee that a layer finishes. The engine CLI defaults to
four workers; the example explicitly limits concurrency to one.

| Exit code | Meaning |
|---|---|
| 0 | Operation succeeded; work remains |
| 2 | Execution/test failure or dependency defer |
| 3 | All slices integrated and verified |
| 4 | Lead repair required |
| 5 | Invalid plan/state, prerequisite, lock or admission/budget block |
| 6 | Accepted commits await integration |

A step does not merge into the user's checkout. Integration verifies accepted
commits in an owned worktree and records its ref/SHA. Review that ref and merge
explicitly into the intended clean branch. Dependent slices wait for verified
integration. [Two worked host examples](docs/WORKED-EXAMPLES.md).

## Validation, costs and recovery

Validation defaults to `--validation-policy deny`: needed validation is a gate
5 block, never automatic permission to spend. `unmetered` permits catalogued
free/flat validation; `allow` permits metered or unknown-cost validation.
Current evidence is keyed by exact spec and CLI/config/account context, and
expires after 30 days by default. Catalog labels alone cannot bypass validation.

`--budget-attempts` counts validation, production and retries.
`--budget-tokens`/`--budget-cost` require positive per-call reservations
(`--attempt-tokens`/`--attempt-cost`). These are admission limits, not provider
hard caps; overruns block subsequent calls. Missing usage is **unknown**, never
zero or inferred from a subscription. Under a usage ceiling, unknown completed
usage blocks by default; `--unknown-usage reserve` explicitly charges the
recorded allowance. [Budget details](skill/references/delivery-core.md).

Resume the same plan/repo/ledger. `--status --json` reads durable state without
inference. `--migrate-ledger`, `--reconcile-plan` and `--new-build` are explicit
state operations with backups, not dispatch commands. A changed plan requires
reconciliation; do not erase the ledger. For gate 4, inspect the retained attempt,
repair authorized source, then `--mark-repaired <slice-id>` and integrate.
[Recovery and migration](docs/MIGRATION.md).

## Boundaries and evidence

Worktrees are **not security sandboxes**. Executor CLIs and pytest can execute
code with the host user's privileges; provider permission settings differ.
CLD protects candidate collection and integration, not arbitrary host access.
[SECURITY.md](SECURITY.md) and [KNOWN-ISSUES.md](KNOWN-ISSUES.md) state the limits.

If Codex on Windows reports `helper_unknown_error: setup refresh had errors`,
follow [the Windows sandbox troubleshooting guide](docs/CODEX-WINDOWS-TROUBLESHOOTING.md)
before paying for another validation probe.

Offline CI runs the full suite on **Windows/Ubuntu × Python 3.11/3.14**, builds
all eight host/provider bundles, checks committed Claude plugins and packages
the Codex catalog. Recorded Windows standalone CLI/IDE discovery, Claude plugin
discovery, OpenCode and Codex Luna/max live proofs are separate historical
evidence. New fast-tier live service, updated Claude picker discovery, fourth
Codex-plugin discovery, live Claude-lead execution, live mid-process provider
kill, Ubuntu Codex flags/live POSIX dispatch and macOS remain unverified.
[Evidence matrix](docs/plans/codex-support/T19B-MATRIX.md).

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q                     # offline; live evals excluded
python -m cld --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md),
[implementation plan](IMPLEMENTATION_PLAN.md) and
[current handoff](docs/plans/codex-support/HANDOFF.md). MIT licensed.
