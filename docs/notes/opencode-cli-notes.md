# OpenCode CLI — captured facts (opencode 1.17.0)

Captured live 2026-06-12 via:

    opencode run "Reply with the single word: ok" -m opencode/deepseek-v4-flash-free --format json

Sample saved alongside this file: `opencode-run-sample.json`.

## `--format json` is JSONL (newline-delimited events), NOT one JSON object

The output is one JSON object PER LINE — a stream of events. `json.load(whole_file)`
**fails**. The parser must iterate lines and `json.loads` each, tolerating blank lines.

Event types seen (the `type` field): `step_start`, `text`, `step_finish`.

## Token key-path

Tokens live on the **`step_finish`** event at `part.tokens`:

```json
{"type":"step_finish", ...,
 "part":{..., "type":"step-finish",
         "tokens":{"total":8145,"input":8129,"output":2,"reasoning":14,
                   "cache":{"write":0,"read":0}},
         "cost":0}}
```

So: iterate the JSONL, find the event whose `type == "step_finish"` (or `part.type ==
"step-finish"`), read `part.tokens`. Fields: `total, input, output, reasoning`, plus a nested
`cache:{write,read}`. There can in principle be multiple `step_finish` events (multi-step
runs) — **sum** the per-step `input`/`output`/`total` to get the run total.

`part.cost` (float, dollars) is also present per step — `0` for the free model. Summable the
same way; useful for the premium-metered cost guardrail later.

## parse_opencode_usage target shape

`parse_opencode_usage(raw_json: str) -> dict[str, int]` should return e.g.
`{"input": 8129, "output": 2, "total": 8145, "reasoning": 14}` for this sample
(single step → those exact numbers). Return `{}` on unparseable/empty input.

## Windows

`opencode` resolves on PATH directly here (no `.cmd` shim needed in Git Bash). For the
subprocess runner on Windows, prefer `opencode.cmd` with an `OPENCODE_CLI_CMD` override,
mirroring the `gemini.cmd`/`GEMINI_CLI_CMD` handling.

## Model ids (relevant subset of `opencode models`)

- `opencode/deepseek-v4-flash-free` — free, used for dogfooding (this probe)
- `opencode/deepseek-v4-flash`, `opencode/deepseek-v4-pro`
- `opencode/gemini-3.1-pro`, `opencode/gemini-3-flash`, `opencode/gemini-3.5-flash`
