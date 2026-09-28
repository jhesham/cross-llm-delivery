# Contributing

## Setup and checks

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

The default suite excludes live behavioral evals and needs no provider account
or API key. It uses real Git/subprocess boundaries in temporary repos. Run
focused checks for the changed contract first; Windows/Ubuntu × Python
3.11/3.14 CI is the cross-platform closure gate. Live calls require explicit
authorization, exact model IDs and separately reported usage.

## Layout

- `engine/cld/`: CLI, plans, independent candidate acceptance, durable ledger,
  dependency/integration lifecycle, bounded processes, admission/accounting.
- `engine/cld_providers/<provider>/`: antigravity, cursor, opencode and codex
  adapters plus provider resources. New models need not become static catalog
  entries: an explicit CLI-supported spec still passes normal admission.
- `skill/`: Claude entry template, shared references and vendored driver.
  `skill/hosts/codex/` contains the Codex entry/reference/agent metadata.
- `generator/`: standalone bundles, plugin packages, Codex installer and
  checked release/publishing helpers.
- `docs/plans/codex-support/`: tracker, evidence, handoff and acceptance scope.

Preserve the distinction between lead host and implementation provider.

## Change and regenerate

Behavioral fixes need a meaningful regression: actual return codes, Git
trees/refs, retained bytes, durable state or process boundaries. Do not infer
acceptance from model prose. Optional telemetry must not become an acceptance
dependency. Keep environment/account configuration out of published artifacts.

`dist/` is ignored. `plugins/` is committed Claude generator output; change
source first and regenerate, never edit generated copies:

```bash
python generator/build_skill.py --all
python generator/build_skill.py --all --host codex
python generator/build_plugins.py
python generator/build_plugins.py --host codex
python generator/check_plugins_fresh.py --dist-root dist --plugins-root plugins
```

Keep entry skills concise and YAML-first; route detailed setup/workflow material
to references. Preserve provider names, legacy driver invocation and current
Codex metadata/invocation policy.

## Candidate versus publication

VERSION, project version, package and plugin manifests must agree. A candidate
records source SHA, hashes, migration instructions, checks and support limits.
Preparing or pushing the refactor branch does not authorize merging main,
creating tags/releases, publishing provider mirrors or installing other hosts.
Release helpers reject native-command/CI/version failures; inspect a dry-run
with explicit source/remote/target settings before authorized publication.
See [the candidate record](docs/plans/codex-support/T20B-CANDIDATE.md).

At each authorized task boundary, update the handoff/tracker, commit the
coherent verified changes and stop for the user's token checkpoint.

## Issues

Include OS/Python/host/provider versions, exact executor spec, schema/gate
from `--status --json`, and the relevant attempt's diagnostics/artifact paths.
Redact prompts, credentials and sensitive source before sharing. Security
issues should use the repository's private reporting channel; see SECURITY.md.
