# Field feedback: asx-agent build (2026-07-02) — for the cross-llm build agent

Real-world build: 16-slice plan, Windows, executors cursor:composer-2.5 then opencode.
11/16 slices green. Three issues found live; per the user, fixes belong to this repo's
build agent — the asx-agent orchestrator (Claude) has NOT touched cld code.

## 1. `--step` drops `--executor` → silent fallback to default workhorse (suspected regression)

- Invocation: `run_delivery.py CLD_PLAN.md --repo <dir> --step --workers 1 --executor opencode:opencode/kimi-k2.7-code`
- Observed via `--status`: the slice ran `opencode:opencode/deepseek-v4-pro` with `source: default`.
- Spec parsing itself is fine — verified interactively that
  `parse_executor_spec('opencode:opencode/kimi-k2.7-code')` returns
  `('opencode', {'model': 'opencode/kimi-k2.7-code'})`.
- So the loss is downstream of parsing, somewhere in the `--step` path (echoes the
  S961 hardcoded-default class fixed 2026-06-25; this looks like a refactor regression
  of the same shape: the layer-run path not threading the user spec through).
- Impact: user's explicit model choice is silently ignored — worst kind of failure
  (build proceeds, wrong model, only visible if someone reads `--status`).
- Suggested test: dispatch with a non-default `--executor` in `--step` mode and assert
  the ledger/telemetry event records that exact spec.

## 2. Stale opencode catalog id: `kimi-k2.7` → live Zen id is `kimi-k2.7-code`

- `opencode/kimi-k2.7` (in the vendored catalog) fails at dispatch with a Zen-side
  `{"type":"error","error":{"name":"UnknownError",...}}` — the gateway no longer serves it.
- `opencode models` (CLI v1.17.4) lists: `kimi-k2.5`, `kimi-k2.6`, `kimi-k2.7-code`.
- `opencode/kimi-k2.7-code` validated headless via `cld.validate.validate_model`:
  **verified** (trivial slice built, real test passed, attempt 1). Evidence store updated
  (`~/.cld/validation-evidence.json`): `kimi-k2.7-code: verified`, `kimi-k2.7: untested`.
- Suggested fix: refresh the catalog id (+ consider a periodic catalog-vs-`opencode models`
  drift check, since Zen renames ids).

## 3. Caller-merge contract is easy to miss → dep-blind worktrees (operator trap, docs/design ask)

- `cld.worktree.worktree()` branches each slice from master HEAD; accepted work commits
  to `slice-<id>`; nothing in `run_delivery.py` merges those back. The orchestrating
  agent (caller) must merge between layers — this is only stated in a code comment
  (`orchestrator.py` ~line 341), not in the skill workflow.
- Live consequence: slice T15 failed twice — first `ModuleNotFoundError` on a dep module,
  then the executor rewrote all 12 dep files in its worktree and was (correctly) rejected
  by the diff-rule. Both attempts were doomed regardless of model.
- Mitigating quirk: most dep-blind slices still passed because the plan committed a
  CONTRACTS.md with full reference code, so executors recreated deps inside their own
  allowed files (e.g. T9 shipped a superset ta.py). That's luck of this plan's authoring
  style, not a property of the engine.
- Suggested fix (pick one): (a) orchestrator auto-merges accepted `slice-*` branches into
  the base branch at layer end; or (b) worktrees branch from a layer-integration branch;
  or (c) at minimum, a loud "MERGE ACCEPTED SLICES BEFORE THE NEXT --step" step in the
  generated SKILL.md workflow + a preflight warning when pending layers depend on
  unmerged accepted slices (the ledger has everything needed to detect this).

## Repro context

- Repo: `d:\claude_server\asx-agent` (ledger `.cld-ledger.json`, telemetry `.cld/events.jsonl`,
  run cc695749). T15 detail: `.cld/T15/detail.json` (12 files changed, 475-line diff, rejected).
- The asx-agent build is PAUSED until items 1–2 land (user decision 2026-07-02).
