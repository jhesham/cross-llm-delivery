# OpenCode headless model selection — RESOLVED, works (2026-06-13)

## The proven fact

**`opencode run -m <model>` WORKS reliably in headless mode.** The earlier "blocker"
(claimed `-m` is ignored) was FALSE — an artifact of the leaked-server / dispatch-guard
mess at the time, not a real selection failure.

## Proof (dashboard = ground truth, $0 free models)

Six dispatches, every one billed the model passed via `-m`:

| session   | `-m` requested              | model billed (dashboard) |
|-----------|-----------------------------|--------------------------|
| iTUqmAQg  | mimo-v2.5-free              | **mimo-v2.5-free**       |
| T5MQl7LZ  | deepseek-v4-flash-free      | **deepseek-v4-flash-free** |
| Ji7uWi0X  | mimo-v2.5-free              | **mimo-v2.5-free**       |
| vXZJvUsr  | deepseek-v4-flash-free      | **deepseek-v4-flash-free** |
| d7CZfCsn  | mimo-v2.5-free  (config empty)        | **mimo-v2.5-free** |
| Dft22jD2  | mimo-v2.5-free  (config PINNED deepseek!) | **mimo-v2.5-free** |

**Config `model` does NOT override `-m`** either: the last run had the global
`opencode.jsonc` pinned to `deepseek-v4-flash-free` AND `-m mimo` — it billed **mimo**.
`-m` wins.

## Important gotcha: self-reported model ids are UNRELIABLE

When asked "what model are you?", a model may answer a wrong/hallucinated id (one
`mimo-v2.5-free` run replied "mimo-v2-pro-free"). **Never trust the text reply for the
model id — use the billed model on the dashboard, or `parse_opencode_usage`/the JSONL
event metadata.** This mis-led earlier diagnosis.

## Implication: our investment is sound

`--executor opencode:<model>`, `pick_executor`, `recommend`, `browse_models`,
`validate_model` all correctly control which model runs. No executor change needed for
model selection. The picker works.

## Other confirmed mechanics (zero-cost)

- `run --dir X` is authoritative only in ATTACH mode; a plain `run` resolves the project
  from cwd / nearest git root (drifts to enclosing repo). Our serve+attach handles this.
- `build` agent has NO pinned model; blocks external_directory writes -> `ask` (headless
  can't answer) → mitigated with `--dangerously-skip-permissions`.
- `opencode.cmd` shim spawns a real `opencode.exe`; terminating the shim orphans it →
  `_OpenCodeServer.stop()` does Windows tree-kill (`taskkill /F /T`).

## The saga, finally settled

The "mystery deepseek caller" was our OWN test dispatches (process tree confirmed). The
one true anomaly (2:58 tnDwk5e4: mimo→deepseek) was corruption from a leaked server +
dispatch-guard at that instant, never reproduced under clean conditions.

## Method lesson

The billed-model dashboard is ground truth; model self-reports and a single anomalous run
are not. Two clean $0 A/B dispatches (config empty vs pinned, both `-m mimo`) settled what
hours of theorizing could not.
