# cross-llm-delivery — OpenCode executor "dispatch failed" on Windows (engine bug)

> **✅ RESOLVED 2026-06-13 (commit 7e8f1a5).** Your diagnosis was exactly right (see "Most
> likely culprit" below): the long multi-line prompt passed positionally to the `opencode.cmd`
> shim is mangled by `cmd.exe /c`, so the dispatch falls back to interactive mode and emits no
> `step_finish`. **Reproduced live** (short prompt: step_finish=True; same long prompt:
> step_finish=False, 0 bytes, interactive banner in stderr). **Fix:** `_oc_cmd` now resolves
> and invokes the REAL `opencode.exe` behind the npm shim
> (`<npm-prefix>/node_modules/opencode-ai/bin/opencode.exe`), which subprocess runs WITHOUT a
> shell, so the multi-line argv is passed cleanly. Proven: the same long prompt via the .exe
> → rc=0, step_finish present, ~15KB JSONL of real work. Falls back to `.cmd` if the exe isn't
> found; `OPENCODE_CLI_CMD` override still wins. **OpenCode executor is usable again** — the 3
> models you tested (deepseek-v4-pro, kimi-k2.6, deepseek-v4-flash-free) are selectable; their
> "untested" verdicts stand (correctly — no model misbehaved) and can now be validated for real.

**Date:** 2026-06-13 (advisor-graph S12 picker)
**Symptom:** Every OpenCode model fails validation/dispatch with
`ValidationResult(passed=False, status='untested', note='executor dispatch failed (not a model verdict)')`.
Tested 3 models — all identical: `deepseek-v4-flash-free`, `kimi-k2.6`, `deepseek-v4-pro`.

**NOT the cause (all proven working in isolation on this host):**
- `opencode.cmd` is on PATH, version **1.17.4**, authenticated.
- A direct shell run works: `opencode.cmd run "print hi" -m opencode/deepseek-v4-pro --format json --dir . ` → valid JSONL with `step_finish`, tokens, cost (~$0.014). Exit 0.
- The engine's EXACT flag form works too (incl. `--dangerously-skip-permissions` and bare `--port` last): exit 0, `step_finish` present.
- Python `subprocess.run([...], cwd=…, capture_output=True, text=True)` with the engine's exact argv (mimicking `_default_runner`, no `shell=True`) ALSO works: rc 0, valid JSONL.

**So the failure is inside `OpenCodeExecutor.run` / `validate_model`'s real invocation**, not the CLI, model, auth, flags, or basic subprocess. The verdict "executor dispatch failed" is set when `rc != 0` OR no `step_finish` in output (`opencode.py` run()).

**Most likely culprit (to investigate in the engine):**
- The real dispatch builds a **long multi-line prompt** (brief + file list + instructions) and passes it as a single `argv` element to `opencode.cmd`. On Windows, a long/complex string arg through a `.cmd` shim via `CreateProcess` can hit cmd.exe's line-length/escaping limits or quote-mangling where a short trivial prompt does not — producing a non-zero exit or empty output. (My working probes all used SHORT prompts.)
- Worth checking: does `_default_runner` need `shell=False` + a response-file/stdin for the prompt instead of a positional arg? Or write the prompt to a temp file and pass `--prompt-file`-style? Or the `validate_model` trivial-slice prompt may itself be long enough to trip it.

**Repro for the engine maintainer:**
1. `from cld.executors import get_executor; from cld.validate import validate_model`
2. `validate_model("opencode/deepseek-v4-pro", executor=get_executor("opencode", model="opencode/deepseek-v4-pro"), git_runner=<gitrunner>, base_dir=<tmp>)` → "executor dispatch failed".
3. Yet the same `opencode.cmd run …` argv run directly (short prompt) → exit 0.
4. Suspect: capture the EXACT argv the failing run builds (esp. prompt length/content) and the rc/stderr — `OpenCodeExecutor.run` currently discards stderr into raw_log only on failure; surface the actual rc + stderr in the ValidationResult note to confirm.

**Impact:** OpenCode executor unusable on this host until fixed → all non-Gemini picks fail. Gemini (separate CLI path) is the only working executor. Advisor-graph build continues on gemini.

**Action:** pass to the cross-llm-delivery engine session.
