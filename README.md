# cross-llm-delivery (`cld`)

Cross-LLM Delivery lets **Codex or Claude Code lead a build** while a selected
headless CLI implements its slices. The lead writes contracts and committed
acceptance tests; the engine independently verifies each Git candidate, checks
its writable allowlist, and integrates accepted commits against an explicit
test suite. Model output alone never decides acceptance.

**Independent project; not affiliated with or endorsed by Anthropic or OpenAI.
Claude, Claude Code, Codex and other names are trademarks of their owners.**

Use it for contract-driven, multi-slice implementation with committed tests and
independent acceptance/integration. Debugging and tiny edits are better handled
directly by the lead. Privacy: [PRIVACY.md](PRIVACY.md). Security and private
vulnerability reporting: [SECURITY.md](SECURITY.md). Questions and bugs:
[GitHub Issues](https://github.com/jhesham/cross-llm-delivery/issues).

The lead host and implementation provider are separate choices:

| Lead host | Implementation provider |
|---|---|
| Codex CLI or IDE, using a Codex skill bundle | OpenCode, Antigravity, Cursor, Codex CLI or Claude Code CLI |
| Claude Code, using a Claude skill or plugin | The same five providers and engine |

Version **0.4.2** supports both lead hosts and five executor providers,
including the Claude Code CLI executor (your Claude subscription, an isolated
`claude -p` session per slice).
Use the [versioned release and artifacts](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.2)
for a fixed source revision. The Claude-only root marketplace is read from `main`;
both hosts' plugin manifests follow `VERSION`, so Claude marketplace-managed plugin
updates stay pinned until the manifest version changes (local in-place profiles can
differ). Maintainers bump `VERSION` through the existing checked release workflow for
distributable plugin updates; adding the current version is not a new release.
[Publication verification record](docs/plans/v0.4.0-review-fixes/PUBLICATION-0.4.2.md).

## What installing and using it does

- Runs the bundled Python engine locally and launches the selected executor
  CLI under your account and configuration.
- Creates Git worktrees, `refs/cld/*` refs and `.cld/` logs, events and a
  ledger (`.cld-ledger.json` by default; custom ledger paths are possible).
  Durable records have no automatic expiry; successfully collected executor
  worktrees can be removed after the verified candidate and ledger are saved.
- Runs acceptance/integration tests, project commands and Git hooks with your
  user privileges. A worktree is **not a security sandbox**.

There is no publisher-operated service that CLD requires, and the publisher
collects nothing by default. Not all network traffic goes through one CLI: the
selected executor can send prompts and repository content to its configured
provider/endpoints; optional DeepEval Anthropic grading reads
`ANTHROPIC_API_KEY`; OTLP export, only when configured with
`OTEL_EXPORTER_OTLP_ENDPOINT`/`OTEL_EXPORTER_OTLP_HEADERS` or
`LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` (with the OpenTelemetry SDK),
sends model/slice/rung/source/attempt/status/duration/usage metadata, not raw
prompts; project subprocesses can use the network too. Local events are always
recorded during execution. Logs and provider output may contain sensitive data
and are not guaranteed to be redacted; do not paste secrets into plans, briefs,
logs or support requests.

| Executor | Authentication | Billing |
|---|---|---|
| Claude Code CLI | Removes `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`; requires claude.ai subscription login; isolated no-persistence session | Your Claude plan's usage limits |
| Codex, OpenCode, Cursor, Antigravity | Installed CLI with your account/configuration; no removal list applied | Plan, API or provider billing as applicable |

CLD charges no separate inference fee and dollar costs may be unknown. Provider
retention and plan terms follow your provider account; see [PRIVACY.md](PRIVACY.md).

### Reviewer preview (no inference)

Build a bundle, then run the bundled demo plan against an existing Git
repository (absolute path). Claude Code host:

```bash
python generator/build_skill.py claude
python dist/cross-llm-claude/scripts/run_delivery.py dist/cross-llm-claude/examples/demo-plan.md --repo <absolute-git-repo> --host claude-code --dry-run --json
```

Codex host:

```bash
python generator/build_skill.py claude --host codex
python dist/codex/cross-llm-claude/scripts/run_delivery.py dist/codex/cross-llm-claude/examples/demo-plan.md --repo <absolute-git-repo> --host codex --dry-run --json
```

Expected: `"gate_code": 0`, `"run_id": null`, `"layers": [["T1", "T3"], ["T2"]]`.
The preview dispatches no executor, spends nothing on models and writes nothing
to the repository; it is not a live acceptance run or demo build. Every
`dist/cross-llm-<provider>` and `dist/codex/cross-llm-<provider>` bundle ships
a host/provider-specific reviewer README and the same `PRIVACY.md`,
`SECURITY.md` and `examples/demo-plan.md` resources.

## Install and select

You need Python 3.11+, Git, the chosen lead host, and the chosen provider CLI
with suitable authentication. Supported surfaces are local Claude Code and
Codex CLI/IDE workflows, subject to their actual skill/plugin discovery
limitations; ChatGPT web, claude.ai and Cowork are not. Bundles vendor their
engine: no Python package
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

The Codex executor picker uses the installed CLI's local bundled catalog:
run `python scripts/list_models.py --json` inside the `cross-llm-codex` skill.
It offers exact visible model IDs and supported efforts; choices remain
untested until admission. The picker pins `low` where supported (otherwise
`medium`), including for Sol and Astra. Higher effort and `+fast` are opt-in.
The source CLI's interactive Browse option also includes Codex and search.
Discovery does not invoke a model, refresh the catalog or establish pricing.
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
integration. `--gc --repo <dir> --json` previews safe cleanup of CLD-managed
worktrees; add `--apply` to remove them. [Two worked host examples](docs/WORKED-EXAMPLES.md).

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
recorded allowance. Errors that cannot succeed on retry (authentication,
launch, timeout, network, Codex tier warnings) cost one dispatch and stop with
gate 5. [Budget details](skill/references/delivery-core.md).

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
all ten host/provider bundles, checks committed Claude plugins and packages
the Codex catalog. Recorded Windows discovery and live builds include Codex
leads using OpenCode, Codex and Claude executors, and a Claude Code lead using
Codex Luna/max+fast. Those observations are version-specific evidence, not
blanket support claims. Actual fast-tier routing telemetry, later Codex plugin
discovery, full five-plugin IDE discovery, a sandboxed Codex lead for the Claude executor, live mid-process
provider interruption, Ubuntu Codex flag inspection, live POSIX dispatch and
macOS remain unverified. See the [current evidence matrix](docs/SUPPORT-MATRIX.md)
for each host/provider pair and discovery boundary.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q                     # offline; live evals excluded
python -m cld --help
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md),
[implementation plan](IMPLEMENTATION_PLAN.md) and
[current handoff](docs/plans/codex-support/HANDOFF.md). MIT licensed.
