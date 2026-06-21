# Antigravity CLI setup

1. Install the Antigravity CLI; ensure `agy` (or `%LOCALAPPDATA%\agy\bin\agy.exe`) is on PATH.
2. Authenticate once: run `agy` interactively and complete the browser login (reuses `~/.gemini/`).
3. Verify: `agy models` (in an interactive terminal) lists your models.

Windows: the executor runs `agy` with cwd on the C: drive so its transcript path resolves; no action
needed beyond a standard C: user profile. Override the binary with `AGY_CMD` if installed elsewhere.
