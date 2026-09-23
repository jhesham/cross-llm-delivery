# AGENTS.md — maintainer guidance for this repository only

Scope: these instructions apply to the cross-llm-delivery repo alone. Do not copy
user-wide agent instructions here, and do not embed the full initiative plan.

## Entrypoints

- `IMPLEMENTATION_PLAN.md` — initiative plan, scope decisions, reading table.
- `docs/plans/codex-support/HANDOFF.md` — current handoff / restart packet; update
  it at every stopping point.
- `docs/plans/codex-support/TRACKER.md` — task order and completion evidence.

## Source layout

- `engine/cld/` — the delivery engine (provider-agnostic core).
- `engine/cld_providers/<p>/` — per-provider fragments (`antigravity`, `opencode`,
  `cursor`); these three are the only runnable executors.
- `skill/` — Claude skill template and shared references; `skill/hosts/codex/` holds
  the Codex host template.
- `generator/build_skill.py` — generates standalone skill bundles into ignored
  `dist/` (`--host codex` writes `dist/codex/`).
- `generator/build_plugins.py` — packages bundles as plugins: committed Claude
  plugins under `plugins/` (default), or portable Codex plugins plus the local
  marketplace catalog `.agents/plugins/marketplace.json` under an ignored output
  root (`--host codex`, default `dist/plugins`).
- `generator/install_codex.py` — previewable installer for standalone Codex skills.

## Generated-file policy

- `dist/` is gitignored build output; never commit it. Rebuild instead of editing.
- `plugins/` (Claude) is committed generator output: change it only by rerunning
  `python generator/build_plugins.py` after real source changes; the generator
  normalizes banner SHAs so reruns are byte-idempotent.
- Regeneration order: `python generator/build_skill.py --all` (add `--host codex`
  for Codex bundles), then `python generator/build_plugins.py` (or `--host codex`).

## Focused tests

Run only the tests relevant to your change, e.g.:

```bash
python -m pytest tests/test_t13b_marketplace.py -q   # Codex marketplace + repo docs
python -m pytest -q                                   # full offline suite (no evals)
```

Live-LLM evals are excluded by default (`-m 'not eval'`); they need API keys.

## Task checkpoint

Work one committed task slice at a time. When a slice is green, finish its
verification and handoff updates, then stop and ask the user to confirm token
availability before starting the next slice. Do not auto-advance, queue another
dispatch, or treat silence as confirmation; report token usage as measured,
estimated, or unavailable.
