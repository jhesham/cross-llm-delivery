# Cursor CLI — captured facts (cursor-agent 2026.06.12)

Captured live 2026-06-14 via:

    cursor-agent -p --output-format json --force --trust --workspace <dir> "Reply with the single word: ok"

Sample: `cursor-run-sample.json` (alongside this file).

## `--output-format json` is a SINGLE JSON object (NOT JSONL)

Unlike opencode (newline-delimited events), cursor emits ONE JSON object on success:

```json
{"type":"result","subtype":"success","is_error":false,
 "duration_ms":9885,"result":"ok","session_id":"...","request_id":"...",
 "usage":{"inputTokens":14801,"outputTokens":37,"cacheReadTokens":1874,"cacheWriteTokens":0}}
```

So `json.loads(raw)` on the WHOLE output works. Parse it as one object.

## Token key-path (the `parse_cursor_usage` contract)

Tokens live at `usage`:
- `usage.inputTokens` (int)
- `usage.outputTokens` (int)
- `usage.cacheReadTokens` (int)
- `usage.cacheWriteTokens` (int)

`parse_cursor_usage(raw_json) -> dict[str,int]` should return e.g.
`{"input": 14801, "output": 37, "cache_read": 1874, "cache_write": 0, "total": 14838}`
(map the camelCase keys to snake; `total` = input + output). Return `{}` on unparseable/empty.

NOTE on the live sample's exact numbers (for the test's exact-count assertion): input=14801,
output=37, cache_read=1874, cache_write=0 → total (input+output) = 14838. (These come from a
trivial "reply ok" dispatch; the input is high due to cursor's system context.)

## Success signal
`type == "result"` and `is_error == false` and `subtype == "success"`. `result` holds the
model's text reply. A failed dispatch would have `is_error: true` (and likely a non-zero rc).

## No cost field
There is NO cost/dollar field in the JSON (consistent with cursor exposing no headless cost
metric). Per-slice `cost` stays None for cursor.

## ⚠️ KNOWN BUG: long multi-line prompt + headless invocation (2026-06-14)

The CursorExecutor's argv is correct (`--force --trust` present, verified), and **short** prompts
work headlessly. But a **long multi-line slice prompt** breaks dispatch — three invocation forms
tried, each fails:

1. **Positional prompt via `cursor-agent.cmd`** (current executor form): the `.cmd → .ps1 → node`
   shim splats `%*`/`$args`, and the multi-line prompt MANGLES argv so `--trust`/`--workspace`
   don't register → cursor demands "Workspace Trust" and falls back to the cwd (showed OUR repo
   path, not `--workspace`). Same class as the opencode `.cmd` bug.
2. **Direct `node.exe index.js <argv>`** (bypassing the shim, like the opencode `.exe` fix):
   **hangs** (120s timeout) — the `.ps1` sets env the direct call lacks (`CURSOR_INVOKED_AS`,
   `NODE_COMPILE_CACHE`); something waits.
3. **Prompt piped via stdin** (`-p` with no positional, prompt on stdin): **hangs** (120s) — with
   no positional prompt cursor waits for interactive stdin that never resolves.

### ROOT CAUSE (isolated 2026-06-14, after docs research)

Cursor's OWN docs pass multi-line prompts as a positional arg (verified — that's the sanctioned
form, works on mac/linux). Bypassing the Windows shim by calling `node.exe index.js` directly
(with `CURSOR_INVOKED_AS` env + `stdin=DEVNULL` to stop the interactive wait) made SHORT prompts
work (rc=0, result json). But the SAME direct-node path with a LONG multi-line prompt **still
hangs**. So the hang is NOT the `.cmd` shim, NOT stdin, NOT env — it's **cursor-agent itself
hanging on a long/multi-line `-p` prompt without a TTY** (matches the community "-p hangs
indefinitely" bug reports). This is a cursor-agent DEFECT on version 2026.06.12, not something the
executor can cleanly route around. Verdict: cursor cannot reliably run real (long-prompt) slices
headless on this version. Revisit when cursor ships a fix (or a `--prompt-file` input). The
working invocation primitive for SHORT prompts: `node.exe index.js <argv>` + `CURSOR_INVOKED_AS`
env + `stdin=DEVNULL`.

NET: CursorExecutor as built (P2 T2) cannot run a REAL slice yet (real slices = long prompts).
Short-prompt dispatch works, so `--list-models`/`about`/feasibility all fine. The fix is an open
item — candidates not yet cracked: (a) replicate the `.ps1` env for the direct `node index.js`
call; (b) find a `--prompt-file`-style input; (c) a stdin form that also passes a sentinel
positional. The Composer-via-CLI dogfood was deferred because of this (resolve_composer_default
was built by Gemini per the plan's fallback). **All Part-2 NON-dispatch code (catalog, registry,
list_cursor_models, parse_cursor_usage, usage block) is done + tested.**

## Windows
The versioned binary `<LOCALAPPDATA>/cursor-agent/versions/<latest>/cursor-agent.cmd` works; the
top-level shim was broken (replaced with a working one, but the executor resolves the versioned
path itself via _cursor_cmd). Subprocess decodes utf-8/replace (the learned discipline).
