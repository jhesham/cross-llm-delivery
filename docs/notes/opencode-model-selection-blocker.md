# OpenCode headless model selection — BLOCKER (2026-06-13)

## The proven fact

**`opencode run -m <model>` is IGNORED in headless mode.** opencode uses the CLI's
**configured default model** instead of the `-m` flag.

**Proof (zero-cost, free models):** with the opencode CLI default set to
`deepseek-v4-flash-free`, our executor dispatched `OpenCodeExecutor(model="opencode/mimo-v2.5-free")`.
The usage dashboard showed **`deepseek-v4-flash-free`** (the config default), NOT mimo. Requested
model ≠ actual model. Session `tnDwk5e4`, $0.00.

## Why this matters

This breaks the picker + executor model-selection investment: `--executor opencode:<model>`,
`pick_executor`, `recommend`, `browse_models`, `validate_model` all assume the chosen model is
the one that runs. It isn't — every dispatch uses the CLI default regardless.

## What this explained (the whole 2026-06-13 saga)

Every "wrong model on the dashboard" symptom traced to this: kimi requests ran as whatever the
CLI default was (gemini, then deepseek). There was NO external hijacker — the recurring "mystery
deepseek caller" was **our own test dispatches** (confirmed via process tree:
`python _test.py -> opencode serve -> opencode run`, all parented to our script). The dashboard
showed deepseek because `-m` was ignored, not because someone else was calling.

## Confirmed mechanics (all zero-cost, from `opencode --help` / `debug`)

- `run --dir X` is only authoritative in ATTACH mode ("path on remote server if attaching"); a
  plain `run` resolves the project from cwd / nearest git root.
- The `build` agent (default) has NO pinned model (`options: {}`), so the agent isn't the
  override — the **config default** is.
- `build` agent blocks writes outside its allowlist (`external_directory -> ask`); headless can't
  answer, silently blocking writes. Mitigated with `--dangerously-skip-permissions`.
- The `opencode.cmd` shim spawns a real `opencode.exe` child; terminating the shim ORPHANS it.
  A leaked `serve --port 0` kept dispatching for 25+ min. Fixed with Windows tree-kill
  (`taskkill /F /T`) in `_OpenCodeServer.stop()`.

## The fix to investigate next (NOT yet done)

If `-m` is ignored but the **config default IS honored**, the executor should set the model via
a **per-dispatch config** (write a temp `opencode.jsonc` with `"model": <chosen>` and point
opencode at it, or find a `--config`/`--model`-equivalent that actually sticks), instead of `-m`.
Verify with free models (mimo vs deepseek) that the dashboard shows the REQUESTED model before
trusting it. Until then, opencode model selection is unreliable and the picker's OpenCode options
cannot be trusted to run the chosen model.

## Method lesson (for the next session)

Check the **actual process tree and the actual model in the output/dashboard FIRST**, before
theorizing about external causes. This saga burned hours and real $ on six wrong external
theories (TUI hijack, attach mode, another Claude session, claude-mem, OpenCode Zen, cwd) when
one `Get-CimInstance Win32_Process` + reading the dispatched model would have ended it immediately.
