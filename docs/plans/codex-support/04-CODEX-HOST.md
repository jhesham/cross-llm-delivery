# Phase 4 — Codex as the lead agent

Required outcome: a user can open Codex CLI/IDE, invoke the delivery skill, and complete/resume a build with the existing providers. Claude Code remains supported. This phase does not require Codex to implement slices itself. Relevant architecture: A01/A07–A09; version facts are in [SOURCES.md](SOURCES.md).

## T11 — Host-neutral CLI interface

Dependencies: T07/T09/T10. Estimate: 8–14k. Files: `skill/scripts/run_delivery.py`, proposed `engine/cld/cli.py` and `engine/cld/__main__.py`, `summary.py`, `status.py`, CLI contract tests.

- [ ] Move reusable command handling into the engine while keeping the existing script as a thin supported entrypoint; consider `python -m cld` for packaged use.
- [ ] Implement `--json` and the versioned A07 response schema for plan preview, step, integrate, status, usage, and repair/reconcile outcomes. Keep stdout parseable and prompts/banners off it.
- [ ] Include exact accepted refs, next action, run identity, resolved ledger, and artifact paths; keep default responses bounded. Expose optional details by slice/attempt rather than dumping all logs.
- [ ] Remove Claude-specific runtime assumptions: no Claude binary/API/key needed to construct commands, judge deterministic tests, inspect state, or resume.
- [ ] Include optional `host` provenance in telemetry without letting host identity affect acceptance. Clarify missing permission/auth/model policy as structured errors.
- [ ] Test the old script and new entrypoint against the same command/result matrix; preserve established arguments and truthful exit meanings. Verify a no-TTY process never asks for input.

**Gate:** Both lead hosts can consume the same deterministic JSON transcript. A failing/repair/integration-required result cannot be misread as success. R06 compatibility is explicitly covered.

## T12 — Host-aware skill generation

Dependencies: T11. Estimate: 10–16k. Files: `generator/build_skill.py`, `generator/build_plugins.py`, `skill/SKILL.template.md`, proposed `skill/hosts/*`, shared references, generator tests.

- [ ] Extract shared workflow instructions and add explicit host overlays. Keep provider setup/catalog content separate from lead-host wording.
- [ ] Add `--host claude-code|codex`, retaining Claude output defaults and existing plugin IDs/layout. Produce Codex artifacts in a distinct output root.
- [ ] Generate SKILL.md with YAML frontmatter at the start and provenance after it. Use concise descriptions and primary instructions; move catalogs, repair recipes, and large examples into references.
- [ ] Codex overlay names Codex as lead, uses portable bundle-relative driver commands, interprets JSON gates, honors current session authorization, and references the user's existing project instructions without overwriting them.
- [ ] Generate optional Codex `agents/openai.yaml` only using verified fields. Start with explicit invocation policy for the delivery workflow and clear host/provider naming; avoid ambiguous duplicate installations.
- [ ] Correct bundle instructions that currently require `pip install -e .` or reference nonexistent `skill/scripts` inside generated outputs. A self-contained bundle must actually remain self-contained.
- [ ] Test all 2-host × 3-provider combinations for syntax, no unresolved placeholders, import isolation, reproducibility, valid entrypoint paths, and preservation of Claude behavior. Do not assert byte equality for intentionally changed shared instructions.

**Gate:** Six generated combinations smoke successfully without source checkout dependencies. Required YAML metadata is recognized by the chosen validator and later confirmed by actual host discovery. R07 is separately verified by wheel testing in T17.

## T13 — Codex installation and discovery

Dependencies: T12. Estimate: 8–14k. Files: installer/generator helpers, proposed Codex plugin output, `INSTALL.md`, new Codex setup reference, repository `AGENTS.md` if useful, install tests.

- [ ] Provide a repository-scoped standalone installation path under `.agents/skills` and a documented user-scoped alternative; recheck current official discovery behavior before coding. Never assume the app's internal cache path is a public installation contract.
- [ ] Implement a previewable copy/install operation with exact target paths, containment checks, collision reporting, and upgrade/uninstall ownership metadata. Preserve unrelated skills, project instructions, and local edits.
- [ ] Test nested-cwd discovery, path spaces, same-name collisions, fresh install, update, uninstall, and read-only target. Prefer copy fallback where Windows symlinks require privileges.
- [ ] Provide additive Codex plugin packaging for supported surfaces using the currently verified schema. Keep standalone skills as the IDE route; do not require the IDE to support plugins.
- [ ] Add concise maintainer AGENTS.md guidance for this repository only: source locations, generated-file policy, focused checks, and plan/handoff entrypoint. Do not embed the entire initiative or change user-wide AGENTS.md.
- [ ] Verify dry-run/install/uninstall in disposable locations. Actual user-global install is a separate selected target, not a hidden generator side effect.

**Gate:** An isolated Codex setup can discover the generated skill and resolve its scripts. Record host/version/path evidence; no existing Claude installation changes. Installation instructions cover source bundle, repo-local skill, and supported plugin routes accurately.

## T14 — Cross-host acceptance

Dependencies: T13/T17. Estimate: 10–16k. Files: `tests/integration/`, recorded CLI responses, host acceptance checklist/examples, setup documentation. Install/run in disposable test projects.

- [ ] Create a small two-layer sample with committed acceptance tests and deterministic fake provider, exercising plan→step→integrate→status→stop→resume→complete.
- [ ] Run that flow from a different cwd and from a fresh lead session using only the handoff/ledger. Verify no duplicate dispatch or reliance on conversation history.
- [ ] Confirm Codex can discover and invoke the skill from CLI and IDE standalone installation. Capture bounded evidence of script path resolution, permission handling, and gate interpretation.
- [ ] Check Claude Code discovery/driver behavior remains valid with existing names. Automated bundle tests supplement, but do not impersonate, actual host discovery evidence.
- [ ] Exercise each existing provider through contract fixtures under both generated host variants; do not multiply paid live runs across every combination merely because templates differ.
- [ ] When live calls are authorized and credentials are available, run one minimal canary with a selected existing provider, then interrupt/resume safely. Record CLI/host/model/platform, attempts, actual usage if exposed, and unknown costs explicitly.
- [ ] Test sandbox denial: report the needed capability without silently broadening permissions. Verify a worktree root can be configured inside the allowed workspace.

**Gate:** M4 passes offline cross-host tests and recorded discovery evidence. If a host/platform/live account is unavailable, keep that specific checkbox pending and narrow the support claim; do not mark it verified from a mocked test. Full offline suite runs once after the final changes.
