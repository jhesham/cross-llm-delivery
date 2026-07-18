# Contributing

## Dev setup & tests

```bash
python -m pip install -e ".[dev]"
python -m pytest            # default run: no API keys or executor CLIs needed
```

- Live-LLM behavioral evals are excluded by default (`-m 'not eval'`); run them explicitly with
  `pytest -m eval` (needs an API key).
- `-m 'not integration'` skips the tests that exercise real git/subprocess, if git is unavailable.

## Layout

- `engine/cld/` — the provider-blind engine (orchestrator, judge, ledger, dag, telemetry, status).
- `engine/cld_providers/<name>/` — one package per executor backend (catalog + executor +
  skill fragment). Adding a provider = adding one package that registers via `providers_api`.
  - **Adding a model** usually needs no code at all: any id the CLI exposes works via
    `--executor provider:model` / a slice `executor:` tag. A catalog `ModelInfo(...)` line is
    only for models worth recommending in the picker/routing — a fine one-line first PR, ideally
    after you've validated the model in a real build (the note field should say what you saw).
- `generator/` — builds self-contained per-provider skills into `dist/` (**generated — never
  edit `dist/` by hand**).
- `skill/` — the skill template (`SKILL.template.md`), driver script (`run_delivery.py`),
  references, examples.
- See `skill/references/architecture.md` for the module map.

## Conventions

- **Tests first.** This project's own discipline applies to itself: behavior changes come with a
  committed failing test; fixes come with a regression test that pins the failure mode.
- **Deterministic over plausible.** Judging/verification logic must rest on real signals (exit
  codes, file existence, diffs) — never on parsing prose or trusting self-reports.
- **Best-effort observability.** Telemetry/tracing paths must never raise into a build; guard
  optional imports (`opentelemetry` is optional — the engine runs stdlib-only).
- **Windows + POSIX.** CI runs both. Windows-specific workarounds (shim bypass, stdin
  detachment, cp1252-safe output) carry comments explaining the live failure they fix — keep
  that discipline; these are load-bearing.

## Filing issues

Include: OS, provider + model spec, the `--status` output, and the tail of
`.cld/<slice>/judge-output.txt` if a judge verdict looks wrong. `KNOWN-ISSUES.md` lists
current limitations.
