# Antigravity CLI setup

1. Install the Antigravity CLI; ensure `agy` (or `%LOCALAPPDATA%\agy\bin\agy.exe`) is on PATH.
2. Authenticate once: run `agy` interactively and complete the browser login (reuses `~/.gemini/`).
3. Verify: `agy models` (in an interactive terminal) lists your models.

The executor runs `agy` from its selected home directory and looks for the
transcript under that same home. An explicit `home` passed to the executor
overrides the default for both dispatch cwd and transcript lookup.

On Windows, the transcript uses a POSIX-style `/Users/...` path, which resolves
from the current drive root. The executor uses `SystemDrive`; if the profile is
on another drive, it dispatches from a matching `SystemDrive\Users\<name>` path
so transcript lookup resolves. Override the binary with `AGY_CMD` if installed
elsewhere.

On POSIX, the executor uses the native `Path.home()` unchanged and does not
apply `SystemDrive`. Offline path and local-runner checks do not verify live
Antigravity provider behavior on POSIX or macOS.
