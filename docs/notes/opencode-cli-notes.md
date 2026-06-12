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

## CRITICAL: a running opencode TUI captures `opencode run` (attach mode)

Observed live (2026-06-13): with an interactive opencode TUI open elsewhere on the machine,
`opencode run "<msg>" -m opencode/kimi-k2.6 --format json --dir <tmp>` was served by the TUI's
session instead — **agent `build`, model `claude-opus-4-8` (premium, billed), project = the
TUI's directory** (it edited files in an unrelated worktree there). In attach mode `--dir`
means "path on the remote server", `-m` and `--format json` are ignored, stdout is plain text
(no JSONL), and the TUI banner goes to stderr.

**Mitigations (both in `OpenCodeExecutor`):**
1. Always pass bare `--port` (LAST in argv — with no value it picks a random port): forces a
   fresh local server instead of attaching. Verified live: clean JSONL, no banner.
2. Dispatch guard: output without at least one `step_finish` JSONL event → `ok=False`
   ("DISPATCH GUARD ..."), never trusted, no diff captured.

Practical rule: avoid keeping an opencode TUI open at a project root while builds dispatch.

## Windows

`opencode` resolves on PATH directly here (no `.cmd` shim needed in Git Bash). For the
subprocess runner on Windows, prefer `opencode.cmd` with an `OPENCODE_CLI_CMD` override,
mirroring the `gemini.cmd`/`GEMINI_CLI_CMD` handling.

## Model ids (relevant subset of `opencode models`)

- `opencode/deepseek-v4-flash-free` — free, used for dogfooding (this probe)
- `opencode/deepseek-v4-flash`, `opencode/deepseek-v4-pro`
- `opencode/gemini-3.1-pro`, `opencode/gemini-3-flash`, `opencode/gemini-3.5-flash`
