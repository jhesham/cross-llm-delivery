# v0.6.0 design -- Antigravity as a lead host

## Goal

Let Antigravity lead a CLD build the way Claude Code and Codex already do:
author the contracts and tests, step the plan, judge and integrate, with any
supported executor doing the implementation. Existing Claude Code and Codex
bundles stay exactly as they are.

## What each lead host gets

| | Claude Code | Codex | Antigravity (v0.6.0) |
|---|---|---|---|
| Single-executor skills | `cross-llm-<p>` | `cross-llm-<p>` | `cross-llm-<p>-agy` (new) |
| All-executors skill | `cross-llm-delivery` | `cross-llm-delivery` (new) | `cross-llm-delivery-agy` (new) |
| Generated under | `dist/` | `dist/codex/` | `dist/antigravity/` |
| Installer | manual copy | `install_codex.py` | `install_antigravity.py` (new) |
| Repo skills folder | `.claude/skills` | `.agents/skills` | `.agents/skills` |
| User skills folder | `~/.claude/skills` | `~/.agents/skills` | `~/.gemini/config/skills` |
| Plugins | committed, marketplace | local packaging (five) | deferred to v0.6.1 |

## Decisions

- **Separate skill names for Antigravity.** Codex and Antigravity both read
  `<repo>/.agents/skills`, and Antigravity gives repo skills priority over
  user-wide ones. Same-named bundles would let a Codex copy in the repo hide
  the Antigravity copy, so the Antigravity skills carry an `-agy` suffix and
  both can sit in one repo. Codex's bundles are unchanged.
- **Each host sees the other's skill, so both are guarded.** The Antigravity
  bundles ship `agents/openai.yaml` with `allow_implicit_invocation: false`,
  so Codex never invokes them on its own (Antigravity ignores that file). Each
  Antigravity skill page opens by saying it is for Antigravity and names the
  Codex skill to use instead. When a Codex copy is already in the repo, the
  Antigravity installer reports it and tells the user to ask for the `-agy`
  skill by name.
- **One Antigravity dispatch at a time, enforced by the engine, machine-wide.**
  Concurrent `agy -p` children share one local state store and the account's
  limits. The provider declares `max_parallel_dispatches = 1`, and every
  dispatch takes a per-user lock file (the engine's existing `file_owner`
  lock) for its duration. That covers the build default, per-slice tags,
  planner entry and fallback rungs, evidence tasks and model validation, and
  separate builds or CLD processes on the same machine. Other executors in the
  same layer still run in parallel, and judging is never serialised.
  The lock lives in a stable per-user folder (`%LOCALAPPDATA%\cld\locks` on
  Windows, `~/.cache/cld/locks` elsewhere), never under TEMP, which can
  differ per login session or process. `CLD_DISPATCH_LOCK_DIR` overrides it.
  A dispatch waiting for the slot gives up without running when the build is
  cancelled.
- **Claude Code and Codex bundles are pinned.** Tests compare every file of
  every Claude Code and Codex bundle with a snapshot of the v0.5.4 output
  (banner and line endings aside) and the vendored engine with `engine/`.
- **Skills first, native plugins in v0.6.1.** Antigravity's plugin format has
  its own manifest and validator (`agy plugin validate --strict`) and there is
  no Antigravity directory to list in yet.
- **The all-executors bundle for every host.** One install can dispatch Codex,
  Claude, OpenCode, Cursor or Antigravity; the v0.5.4 "No executor chosen"
  refusal keeps it safe. Codex plugin packaging stays at five plugins.
- **Releases and CI build every host.** Release generation and the CI smoke
  build the Antigravity bundles too.
- **No CLI change.** `--host` is already a free-form telemetry label, so
  `--host antigravity` works today and never affects judging or admission.
- **Deprecated `.agent` folder.** Antigravity also reads `.agent/skills`; the
  installer reports an existing same-name copy there and never touches it.

## Host rules the Antigravity skill teaches

- `--step` and `--integrate` write Git worktrees, refs and commits, so they
  cannot run in Antigravity's terminal sandbox (it mounts `.git` read-only).
- A `--step` moves to the background after about ten seconds and the agent is
  woken with its output; end the turn instead of polling.
- On Windows the PowerShell wrapper reports exit 1 for any failure; the JSON
  `gate_code` is authoritative.

## Slices

Layer 1 runs in parallel: `AGYHOSTGEN` (generator host), `AGYINSTALL`
(installer), `AGYSERIAL` (one Antigravity dispatch at a time) and `RELEASEGEN`
(release and CI). Layer 2: `UNIFIEDHOSTS` (all-executors bundle per host),
after `AGYHOSTGEN`. The lead writes the templates, the acceptance tests,
`tests/v060/test_agy_host_e2e.py`, the docs and a live discovery check.
