"""Live validation harness for the antigravity + cursor executors (Task 7).

Runs ONE real executor against a throwaway git worktree and reports whether the
real CLI wrote the file on disk. This calls the REAL CLI (agy / cursor-agent) and
consumes quota; run it in an interactive terminal where you are authenticated.

Usage (from the repo root):
    python smoketest/validate_live.py antigravity
    python smoketest/validate_live.py cursor

It prints PASS/FAIL plus the executor result and whether the target file landed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# make the engine importable without installing
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from cld.executors.base import SliceTask  # noqa: E402


TARGET = "greeting.py"

# A deliberately long, multi-line brief — this is the prompt shape that used to
# break cursor's .cmd shim, so it doubles as the long-prompt regression check.
BRIEF = (
    "Create a small Python module that provides a friendly greeting helper.\n\n"
    "Requirements:\n"
    f"- Create the file `{TARGET}` (and only that file).\n"
    "- It must define a function `greet(name: str) -> str` that returns the\n"
    "  string 'Hello, <name>! Welcome to cross-llm-delivery.' with <name>\n"
    "  substituted in.\n"
    "- It must also define a module-level constant `GREETER = 'cross-llm-delivery'`.\n"
    "- Keep it pure standard library, no external imports.\n"
    "- Do not create any other files.\n\n"
    "This is a tiny task; just write the file directly."
)


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _make_worktree() -> Path:
    wt = Path(tempfile.mkdtemp(prefix="cld_live_"))
    _git(["init"], str(wt))
    _git(["config", "user.email", "live@local"], str(wt))
    _git(["config", "user.name", "live"], str(wt))
    (wt / "README.md").write_text("seed\n", encoding="utf-8")
    _git(["add", "-A"], str(wt))
    _git(["commit", "-m", "seed"], str(wt))
    return wt


def _make_executor(provider: str):
    if provider == "antigravity":
        from cld_providers.antigravity.provider import AntigravityExecutor
        return AntigravityExecutor()
    if provider == "cursor":
        from cld_providers.cursor.provider import CursorExecutor
        return CursorExecutor()
    raise SystemExit(f"unknown provider {provider!r}; use 'antigravity' or 'cursor'")


def main(argv):
    if len(argv) != 2 or argv[1] not in ("antigravity", "cursor"):
        raise SystemExit("usage: python smoketest/validate_live.py <antigravity|cursor>")
    provider = argv[1]
    ex = _make_executor(provider)
    wt = _make_worktree()
    task = SliceTask(id="LIVE", brief=BRIEF, files=[TARGET],
                     acceptance_test_path="(none — manual validation)")

    print(f"[{provider}] dispatching real CLI against {wt} ...", flush=True)
    res = ex.run(task, str(wt))

    target = wt / TARGET
    on_disk = target.exists()
    print("\n================ RESULT ================")
    print(f"provider        : {provider}")
    print(f"executor ok     : {res.ok}")
    print(f"files_changed   : {res.files_changed}")
    print(f"{TARGET} on disk: {on_disk}")
    if on_disk:
        print(f"--- {TARGET} content ---")
        print(target.read_text(encoding='utf-8', errors='replace'))
    print("--- raw_log (first 1200 chars) ---")
    print((res.raw_log or "")[:1200])
    print("--- diff (first 800 chars) ---")
    print((res.diff or "")[:800])
    print("========================================")

    passed = bool(res.ok and on_disk)
    print(f"\n{'PASS' if passed else 'FAIL'} — worktree left at: {wt}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
