# Install Cross-LLM Delivery

Choose the **lead host** (Codex or Claude Code) and **executor provider**
(antigravity, cursor, opencode, codex or claude) independently. Each generated skill
contains its selected provider and the same engine. Python 3.11+ and Git are
required, together with the authenticated provider CLI. Node/npm requirements
depend on the installed provider distribution.

## Build and transfer a coherent set

Build from a committed source revision. `dist/` is ignored generated output;
never copy a stale folder left from another engine version.

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex
python generator/check_plugins_fresh.py --dist-root dist --plugins-root plugins
```

Claude bundles: `dist/cross-llm-<provider>`. Codex bundles:
`dist/codex/cross-llm-<provider>`. Record the generated SKILL banner source SHA.
When switching providers across slices sharing a ledger, update all installed
bundles together from that revision. Provider-specific code differs; shared
engine files must match. Stop active writers before replacing an installation
and preserve the old folders/configuration as backups. Restart the lead host
after installing/updating.

For version 0.4.2, download the coherent host bundle set from the
[versioned release](https://github.com/jhesham/cross-llm-delivery/releases/tag/v0.4.2)
and verify its SHA-256 manifest. The
[publication record](docs/plans/v0.4.0-review-fixes/PUBLICATION-0.4.2.md) records
verification of the tagged source and downloadable assets. The complete set
contains ten standalone bundles: five providers for each of the two lead hosts.

## Claude Code standalone skills

For a **new** installation, copy the chosen `dist/cross-llm-<provider>` folder
into `~/.claude/skills/`. On Windows this is
`%USERPROFILE%\.claude\skills\`.

```powershell
$destination = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force $destination | Out-Null
# Fresh destination only; move an existing installation to a backup first.
Copy-Item -LiteralPath "<source>\dist\cross-llm-codex" -Destination $destination -Recurse
```

```bash
mkdir -p ~/.claude/skills
# Fresh destination only; back up an existing folder first.
cp -R "<source>/dist/cross-llm-codex" ~/.claude/skills/
```

Use the same procedure for the other providers. Avoid overlay copies on an
existing bundle: deleted engine files could remain and mix versions. The folder
must contain YAML-first `SKILL.md` and `scripts/run_delivery.py`.
In a new session ask Claude Code to use `cross-llm-codex` (or the chosen name).
A copied file alone is not observed picker discovery.

## Claude Code plugins

The repo is also a Claude marketplace. In Claude Code:

```text
/plugin marketplace add jhesham/cross-llm-delivery
/plugin install cross-llm-opencode@cross-llm-delivery
/plugin install cross-llm-antigravity@cross-llm-delivery
/plugin install cross-llm-cursor@cross-llm-delivery
/plugin install cross-llm-codex@cross-llm-delivery
/plugin install cross-llm-claude@cross-llm-delivery
```

Install only the providers you need. These commands follow the marketplace's
default-branch version; use the tagged release artifacts to pin a fixed revision.
The source generator produces all five Claude packages under `plugins/`.
Claude manifests intentionally omit a fixed version so Git-commit updates
remain available; generated skill banners record the engine/product version.
Codex portable manifests carry the product version (0.4.2 for this release).

## Codex standalone skills: CLI and IDE

Use the safe installer with an explicit scope root. A repository root installs
under `<repo>/.agents/skills/`; a user-home scope installs under
`<home>/.agents/skills/`. No destination is inferred from environment variables.

```bash
python generator/install_codex.py --preview --scope-root <target-repo> --bundle dist/codex/cross-llm-opencode
python generator/install_codex.py --install --scope-root <target-repo> --bundle dist/codex/cross-llm-opencode
```

For a user install, explicitly replace `<target-repo>` with the user home.
Modified/unowned/linked installations are refused; preserve changes and review
the ownership manifest instead of forcing an overwrite. To remove a clean
owned install:

```bash
python generator/install_codex.py --uninstall --scope-root <target-repo> --name cross-llm-opencode
```

In a new Codex CLI or IDE session invoke `$cross-llm-opencode` (or the selected
skill). Standalone skill discovery has recorded Windows CLI/VS Code evidence;
inspect the actual host if discovery fails. The user's project instructions
are retained. Do not install over `AGENTS.md`.

## Codex plugin surface

Packaging is distinct from host installation:

```bash
python generator/build_plugins.py --host codex
codex plugin marketplace add <absolute-path-to-dist/plugins>
codex plugin list
```

The generated root includes `.agents/plugins/marketplace.json` with contained
local sources. Use the installed CLI's supported plugin installation flow.
Recorded discovery covered the original three plugins on Windows; the later
Codex and Claude executor plugins and IDE plugin surface remain unverified.
Five-plugin packaging is verified separately in the [support matrix](docs/SUPPORT-MATRIX.md).
For the IDE, use the
standalone skill path above rather than assuming plugin discovery.

## Executor setup and read-only verification

Read `references/provider-setup.md` in the chosen generated bundle. It preserves
provider-specific authentication, command overrides and observed CLI caveats.
CLI `--version`/`--help` checks do not establish model/account entitlement.
A model listing is also not a successful validation.

From the installed skill directory:

```bash
python scripts/run_delivery.py --help
python scripts/run_delivery.py <absolute-plan.md> --repo <absolute-repo> --dry-run --json
```

These do not dispatch a provider. A real build requires an exact supported
executor spec and an explicit validation policy under the user's existing
authorization. Codex examples: `codex:gpt-6-luna@max` or, when explicitly
requested, `codex:gpt-6-luna@max+fast`. There is no Codex default model or
entitlement guarantee. For larger max-effort slices, explicitly set
`CLD_DISPATCH_TIMEOUT=1200` before the driver; default dispatch/probe deadlines
are 600/30 seconds. Do not automatically raise budgets or retry.

See [worked examples](docs/WORKED-EXAMPLES.md), [migration](docs/MIGRATION.md)
and [support limits](KNOWN-ISSUES.md). An older ledger is not made compatible
by copying a newer skill over it; migrate with backups first.
