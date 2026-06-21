# Antigravity CLI (`agy`) — headless dispatch notes

**Status (2026-06-22): headless dispatch SOLVED on Windows.** These are the working primitives for
building the future `antigravity` provider (`cld_providers/antigravity/`). Replaces the deprecated
Gemini CLI. See [[project_gemini_cli_deprecated]] / STATUS.md post-rebuild queue.

## The binary
- `C:\Users\Administrator\AppData\Local\agy\bin\agy.exe`, v1.0.10. On the user PATH.
- Auth: interactive first-run login (browser OAuth, Google). **Reuses the `~/.gemini/` dir**
  (`~/.gemini/antigravity-cli/...`). No `login`/`auth` subcommand.
- Relevant flags: `-p`/`--print`/`--prompt` (non-interactive single prompt), `--model`,
  `--add-dir <dir>` (workspace, repeatable), `--dangerously-skip-permissions` (auto-approve tools),
  `--log-file <path>` (debug log), `--print-timeout` (default 5m). Subcommands: `models`, `update`,
  `plugin`, `changelog`, `install`.

## THE WINDOWS GOTCHA (root cause of "no headless output")
`agy` writes the model's reply to a **transcript file**, not to stdout. The transcript path is built
**POSIX-style**: `/Users/Administrator/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript.jsonl`.
On Windows a leading-`/` path resolves to the root of the **current drive**. If cwd is on `D:`, it
becomes `D:\Users\Administrator\...` which does not exist → repeated
`open ...transcript.jsonl: The system cannot find the path specified` → nothing is written → `-p`
prints nothing and `agy models` is empty.

**Workaround: run `agy` with the working directory on the C: drive** (e.g. cwd = `C:\Users\Administrator`).
Then `/Users/Administrator/...` resolves to the real `C:\Users\Administrator\.gemini\...`, the
transcript is written, and the dispatch completes. (The model call itself — `streamGenerateContent` —
always worked; only the local transcript write was broken.)

## Working headless recipe (verified 2026-06-22)
1. Launch `agy.exe -p "<task prompt>" [--model <m>] [--add-dir <worktree>]` with:
   - **WorkingDirectory on C:** (`C:\Users\Administrator`),
   - stdin CLOSED (it waits on a TTY otherwise; close stdin → it proceeds),
   - stdout/stderr redirected (Python: `encoding="utf-8", errors="replace"`).
   - stdout is EMPTY by design — do not rely on it.
2. After exit (rc 0), find the NEWEST transcript:
   `C:\Users\Administrator\.gemini\antigravity-cli\brain\<id>\.system_generated\logs\transcript.jsonl`
   (sort by mtime; each `-p` invocation creates a new `<id>`).
3. Parse the JSONL. Each line is a step `{step_index, source, type, status, content, thinking, ...}`.
   The model's reply = the `content` of the step(s) with `"source":"MODEL"` (e.g.
   `"type":"PLANNER_RESPONSE"`). Tool actions appear as their own steps; real file edits land on disk
   in the workspace (`--add-dir`).

Verified: prompt "Reply with exactly one word: READY" → transcript step_index 3
`{"source":"MODEL","type":"PLANNER_RESPONSE","content":"READY"}`. Default model selected:
**"Gemini 3.1 Pro (High)"**. Antigravity also exposes **Claude models** (per user) — enumerate via
`agy models` run in a REAL interactive terminal (the `models` subcommand is TTY-only; headless it
exits 0 with no output, same path-class issue). The provider catalog = "whatever `agy models` lists".

## Provider build decisions (user-confirmed 2026-06-22)
- Build a **NEW `cld_providers/antigravity/` provider** (do not repurpose the `gemini` one; it stays as
  a disabled/historical adapter).
- Catalog = whatever `agy models` reports (Gemini-family + Claude).
- Executor adapter mirrors the recipe above (cwd-on-C:, stdin closed, transcript-read capture). This
  is the SAME class of fix as the cursor direct-node work ([[project_cursor_dispatch_open_item]]).

## Open questions for the build
- Does `--add-dir <worktree>` + a multi-file edit prompt produce on-disk diffs in the worktree (the
  slice-execution path)? (the READY test was text-only — needs a real file-write test.)
- Per-dispatch model selection: `--model "<label>"` — confirm exact id strings from `agy models`.
- Quota/usage surfacing for the `account_section` (the log shows `quota_manager` — may be queryable).
- Can `--print-timeout` + transcript polling stream progress, or only read-after-exit?
