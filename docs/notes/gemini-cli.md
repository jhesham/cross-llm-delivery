# Gemini CLI — locked invocation reference

Verified on this machine 2026-06-08.

- **Binary:** `gemini` (Windows native, no WSL) — `C:\Users\Administrator\AppData\Roaming\npm\gemini.ps1`
- **Version:** 0.45.2
- **Auth:** working (headless `gemini -p "..."` returns output).

## Flags (confirmed via `gemini --help`)

| Flag | Purpose |
|---|---|
| `-p` / `--prompt` | headless / non-interactive mode |
| `-m` / `--model` | select model |
| `-y` / `--yolo` | auto-approve ALL actions (full autonomy) |
| `--approval-mode` | `default` \| `auto_edit` (auto-approve edits only) \| `yolo` \| `plan` (read-only) |
| `-o` / `--output-format` | `text` \| `json` \| `stream-json` |

## Model ids (probed)

- `gemini-3.1-pro-preview` ✅ **← executor model for this project (== "Gemini 3.1 Pro")**
- `gemini-3-pro-preview` ✅ (alternative Pro)
- `gemini-3.1-flash-lite` ✅ (CLI's internal utility router)
- `gemini-3-flash-preview` ✅ (CLI default main)
- `gemini-3.1-pro` ❌ 404 ModelNotFoundError
- `gemini-3-pro` ❌ 404

## Headless executor invocation (use this form)

```powershell
gemini -p "<task>" -m gemini-3.1-pro-preview --approval-mode auto_edit -o json
```

- Use `--approval-mode auto_edit` for the executor (auto-approves file edits, the only
  tool class it needs) rather than full `yolo`, for a tighter blast radius.
- `-o json` returns `stats.models.<id>.tokens` (input/prompt/candidates/total/cached/
  thoughts) per model — **this is our token-cost capture for the judge step (Task 0.5).**
- Note: CLI emits harmless warnings ("256-color", "Ripgrep not available") on stderr.
