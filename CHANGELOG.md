# Changelog

Format: [Keep a Changelog](https://keepachangelog.com). Add lines under **Unreleased** as
changes land; on a release, rename that section to the version + date. Plugin installs track
`main` per-commit; release tags are human milestones.

## [Unreleased]

### Added
- Community scaffolding: SECURITY.md (private vulnerability reporting + threat-model notes),
  bug-report issue form (asks for `--status` + judge output up front), PR template carrying the
  failing-test-first convention, and issue links routing questions to Discussions.

### Changed
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
