# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Add lines under **Unreleased** as
changes land; on a release, rename that section to the version + date. Plugin installs track
`main` per-commit; release tags are human milestones.

## [Unreleased]

### Fixed
- OpenCode uses one native launcher for dispatch, discovery, stats and preflight
  (review N07): explicit absolute override, Windows `opencode.exe` on PATH, then
  npm's installed native target. Native-only installations are recognized;
  incomplete installs and Windows `.cmd`/`.bat` overrides fail with native-path
  guidance. No shell fallback; long/multiline argv and injected runners remain
  compatible. The shared Codex/Claude launcher also rejects Windows shim overrides.
- All five executors mark production children with `CLD_EXECUTOR_DEPTH=1`
  and reject nested direct dispatch before probes or artifact creation (review
  N06). Only an absent marker or literal `0` identifies a lead. OpenCode, Cursor
  and Antigravity prompts now prohibit recursive delegation; provider environment
  adjustments and legacy injected runners remain compatible.
- Codex validation evidence now includes selected home, conservative project
  layers and native managed configuration files, including missing-file states
  and referenced credential/header environment variables. Changes block saved
  evidence and already-admitted factories before dispatch (review N05). Relative
  `CODEX_HOME` values are refused because validation and execution use different
  worktree directories; configuration bytes and secret values are never recorded.
- Acceptance runs bind project imports to the frozen Git candidate, including
  inherited `PYTHONPATH`, editable installs and namespace packages. Code loaded
  from a live checkout at startup or through a late import hook blocks acceptance
  instead of approving a different tree (review N04). External dependencies remain
  available. Delivery, repair, integration and validation share this policy.

## [0.4.1] — 2026-10-03

### Fixed
- Claude executor: the selected effort is authoritative. The child's
  `CLAUDE_CODE_EFFORT_LEVEL` is pinned to the spec's effort, because Claude Code
  gives that variable precedence over `--effort`; a lead session's ambient value
  could otherwise run a `@low` executor at `max` (review N01).
- Claude executor: login and usage-limit diagnostics are classified even when the
  process runner labels the exit `nonzero_exit`, so an expired login or a limit
  hit mid-build stops after one dispatch (final error, gate 5) instead of
  retrying and escalating; a nonzero exit is never a candidate (review N02).
- OpenCode: `{env:NAME}` references inside inline `OPENCODE_CONFIG_CONTENT`
  now key validation evidence like file-based references, so a changed
  credential or endpoint is revalidated (review N03).

## [0.4.0] — 2026-10-03

### Added
- **Claude Code executor** (`--executor claude:<exact-model-id>@<effort>`): Codex
  or Claude leads dispatch slices to Claude models through the logged-in
  `claude` CLI on the user's subscription. Each dispatch is an isolated
  `claude -p --safe-mode --restricted` session (no hooks, plugins, skills, MCP,
  CLAUDE.md or saved session), prompt on stdin, API-key variables removed,
  exact IDs only (aliases rejected), curated picker menu, model-free login and
  capability preflight, account-aware validation evidence. New final errors:
  `usage_limit`, `model_mismatch`, `not_logged_in`. Live-verified on Windows,
  including a Codex-lead two-slice build.
- Shared native-CLI launcher used by the Codex and Claude providers.

### Fixed
- `--gc` safety (review R01, R02, R04, R05): a worktree's slice is identified
  from its recovery evidence, never the truncated branch slug, and is kept when
  that is not provable; each candidate is decided and removed under its slice's
  owner lock, so an active delivery's worktree is kept; a ledger bound to a
  different repository blocks (gate 5) with no removals; ignored local data
  counts as dirty (disposable tool caches excepted) for every candidate; an
  earlier build's integration worktree is removed only after it passed or failed.
- OpenCode credentials and endpoints referenced from its config as
  `{env:NAME}` now key validation evidence (values hashed, never stored)
  through a new provider `config_env` hook (review R03).
- Network failures printed late in long output, or on stderr, are classified
  from the retained full stdout/stderr tails, so they stop after one dispatch
  instead of retrying and escalating (review R06).
- Codex native launching no longer depends on the Git runner (review R07).
- Wheel/sdist package data includes the Claude provider's resources.

### Documentation
- Layered plans: the frozen integration selector must stay green after every
  layer. Codex leads on Windows act on the JSON `gate_code`, not the shell exit.

## [0.3.1] — 2026-09-30

### Fixed
- Validation evidence is keyed only on provider-declared environment variables
  plus proxy/certificate settings. Per-session host variables no longer force a
  paid revalidation in every new lead session. Context contract 2: existing
  evidence is stale once.
- New, untracked tool caches and packaging metadata (`.mypy_cache`,
  `.ruff_cache`, `.hypothesis`, `.tox`, `.nox`, `htmlcov`, `.eggs`,
  `*.egg-info`, `.coverage*`, `CACHEDIR.TAG` directories) no longer reject a
  correct slice. The judge snapshot checks tracked candidate files only, so
  projects whose tests write `.hypothesis` or `.coverage` can use CLD; new
  judge-created files are listed in attempt evidence.
- Final executor errors (authentication, missing binary, access denied, launch,
  missing capability, invalid invocation, recursion, Codex service-tier
  warning/mismatch, timeout, network unavailable, diff capture) cost one
  dispatch: no retry, no escalation, gate 5, slice resumable.
- The Codex executor resolves the native binary without a shell
  (`CODEX_CLI_CMD`, `codex.exe`, or the npm package's native executable); a
  shim-only Windows install blocks with an actionable message instead of a
  false "missing binary".
- Codex picker labels keep their text (no cp1252 re-encoding).
- `deliver_slice` no longer fabricates a Gemini model name; an explicit
  `--executor` is recorded as source `chosen` (#12).

### Added
- `--gc` previews safe cleanup of CLD-managed worktrees; `--gc --apply` removes
  integrated and superseded integration worktrees (`--include-previous` adds
  clean earlier-build ones). Evidence and refs are never removed.
- Codex-lead guidance: dispatching commands need network access; CLD blocks
  before dispatch when `CODEX_SANDBOX_NETWORK_DISABLED=1`.

## [0.3.0] — 2026-09-29

- Codex CLI/IDE and Claude Code lead the same engine through independent
  acceptance, durable state and verified integration. Eight standalone bundles
  and four plugin packages per host; explicit Codex model selection is required.
- Added the optional Codex executor with bounded ephemeral/stdin dispatch,
  recursion refusal, feature checks and usage parsing. Explicit
  `codex:gpt-6-luna@max+fast` preserves effort/tier and separate admission
  evidence; exposed warning/fallback output fails before candidate capture.
- Schema-2 build identity, atomic/locked persistence, explicit legacy migration,
  plan reconciliation, per-attempt recovery evidence and checked durable refs.
- Independently reconstructed candidate trees, protected committed acceptance
  inputs, checked test collection/exit codes, dependency integration boundaries,
  retained repair work and truthful JSON gates.
- Context-bound model validation with explicit spend policy, persisted usage
  reservations/unknown accounting, bounded process-tree termination and guarded
  native-command/release/CI handling.
- Concise YAML-first Claude entries; provider/setup detail loads by reference.
  Documentation separates host/provider, acceptance/integration, candidate/release,
  and offline/discovery/live evidence. VERSION/package/Codex plugin metadata is
  0.3.0; Claude manifests retain their Git-commit update policy.
- Full offline CI on Windows/Ubuntu and Python 3.11/3.14. Recorded live Windows
  OpenCode and tier-unspecified Codex Luna/max remain distinct from unverified
  fast service, live Claude-lead execution, live POSIX and macOS surfaces.
- Fixed Claude marketplace omission of the fourth Codex plugin. Checked
  release validation now accepts intentionally Git-versioned Claude manifests
  only with a matching generated skill banner; stale/missing/null version
  evidence still fails. Codex manifests keep explicit semantic versions.

### Added
- Community scaffolding: SECURITY.md (private vulnerability reporting + threat-model notes),
  bug-report issue form (asks for `--status` + judge output up front), PR template carrying the
  failing-test-first convention, and issue links routing questions to Discussions.

### Changed
- T03 source engine: check collection commit/tree and durable refs before marking a slice
  done. Commit-hook changes are rejected; valid no-op and executor-created commits are
  reused. Worktree cleanup follows the final ledger save; failures retain their paths.
- Per-attempt recovery evidence replaces overwritten slice-level patches/judge logs.
  Binary patches are reconstructed against the original base for verification. A saved
  collected outcome can repair an interrupted final ledger write without redispatching.
- T02 source engine: real delivery now requires a Git runner and independent acceptance
  runner. Report-only Python test doubles must opt into `simulation=True`; serial
  `run_plan` uses the same verified worktree path as parallel delivery.
- Acceptance inputs must be committed before dispatch. The engine checks the baseline,
  captures changes against its original commit, and judges an isolated Git snapshot.
  Tests, pytest configuration and declared `protected_inputs` cannot be executor edits.
  No-change success requires `allow_already_satisfied: true` and a passing baseline.
  See [T02 evidence](docs/plans/codex-support/T02-EVIDENCE.md) for compatibility limits.
- Catalogued `opencode/glm-5.2` (validated in real dogfood builds: 5+ slices, all attempt-1) —
  it now appears in the picker and routing instead of requiring a manual tag.
- README/CONTRIBUTING now state explicitly that **new models need no code changes** — any id the
  executor CLI exposes works via `--executor`/slice tags with the validate-before-trust probe;
  the catalog is curated recommendations only.

## 0.2.0 — 2026-07-06

### Added
- **Self-hosted plugin marketplace** — the repo now doubles as a Claude Code marketplace:
  `/plugin marketplace add jhesham/cross-llm-delivery` then `/plugin install
  cross-llm-<provider>@cross-llm-delivery`. Three per-provider plugins; every push is a new
  installable version.
- **"Using it" guide** in the README — the conversational flow (plan with Claude → "use
  cross-llm-<provider> to run this plan" → Claude delivers + judges).
- **Git preflight** — a missing `git` or a non-git target now aborts with a clear message
  (install hint / `git init`) instead of a raw traceback on the first slice.

### Changed
- README depth pass: badges, real `--status`/gate output samples, a "Safety rails" section, a
  providers/models table with validation status, an honest "Is this for you?" filter, and a
  neutral design-stance section (no comparative claims about other projects).

### Fixed
- `--status` elapsed time was always `0s` from the CLI (now defaults to wall-clock).
- `--executor <provider>:<model>` with an explicit model is honored verbatim instead of being
  silently routed to a catalogued workhorse; stale `kimi-k2.7` catalog id → `kimi-k2.7-code`.
- First CodeQL scan findings (read-only CI workflow token); clean-machine CI failures.

### Security
- Enabled repo secret scanning + push protection, private vulnerability reporting, CodeQL,
  Dependabot; neutral commit identity enforced.

## 0.1.0 — 2026-07-03 (initial public release)

- **Provider-blind engine** (`engine/cld/`): orchestrator with DAG layering + parallel dispatch,
  per-slice git-worktree isolation, resumable JSON ledger, integration gate.
- **Deterministic judge**: committed failing acceptance tests are the dispatch contract; pass/fail
  is the real pytest exit code; an allowed-files diff rule rejects out-of-scope edits; failures
  retry with structured judge feedback.
- **Three executor providers** behind a drop-in registry: **antigravity** (`agy`), **opencode**,
  **cursor** (incl. `cursor:composer-2.5`), each with a model catalog, headless-dispatch quirks
  handled (shim bypass, stdin detachment, console-encoding safety), and validate-before-trust
  probing for untested models.
- **Complexity routing + escalation ladder**: untagged slices route to the cheapest viable model
  and climb on failure; explicit `--executor` models are honored verbatim; per-slice `executor:`
  tags pin a slice.
- **Telemetry**: every lifecycle moment emits to `.cld/events.jsonl`; `--status` digest (layer
  position, in-flight slices + elapsed, tokens, cost-by-model, gate); `--watch` live view;
  opt-in OpenTelemetry export (GenAI semantic spans) to any OTLP backend, with a two-env-var
  Langfuse convenience.
- **Generator**: produces self-contained per-provider Claude Code skills (vendored engine, no
  pip install) into `dist/`, with an optional mirror-publishing helper.
- **Safety rails**: caller-merge preflight (warns when a pending layer depends on accepted but
  unmerged slices), executor-CLI preflight (friendly message instead of a traceback when no CLI
  is installed), non-destructive diff preservation for rejected slices.
